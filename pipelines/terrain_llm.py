"""Structured OpenRouter completions with a run ledger that settles every call to its billed cost."""
import base64
import json
import os
import time
import uuid
from decimal import Decimal
from pathlib import Path

import httpx

from artifacts import canonical, digest
from hybrid_models import assert_wire_schema, strict_schema, unbilled_error

API = 'https://openrouter.ai/api/v1'
PROMPT_CHARS_PER_TOKEN = 3
IMAGE_TOKENS = 2000
ESTIMATE_MARGIN = Decimal('1.5')


class BudgetExceeded(ValueError):
    pass


class Ledger:
    """Append-only JSONL. Spend = settled costs + reservations that never settled (unknown outcome stays counted)."""

    def __init__(self, path, limit_usd):
        self.path = Path(path)
        self.limit = Decimal(str(limit_usd))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _entries(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []

    def spent(self):
        reserved, settled = {}, {}
        for entry in self._entries():
            (settled if 'settled_usd' in entry else reserved)[entry['id']] = Decimal(entry.get('settled_usd', entry.get('reserved_usd')))
        return sum((settled.get(k, v) for k, v in reserved.items()), Decimal(0))

    def _append(self, entry):
        with self.path.open('a') as f:
            f.write(json.dumps(entry, sort_keys=True) + '\n')

    def reserve(self, role, estimate):
        if self.spent() + estimate > self.limit:
            raise BudgetExceeded(f'Budget {self.limit} USD reicht nicht für {role} (Schätzung {estimate:.4f} USD, bisher {self.spent():.4f} USD)')
        call = uuid.uuid4().hex
        self._append({'id': call, 'role': role, 'reserved_usd': str(estimate), 'at': time.time()})
        return call

    def settle(self, call, cost, receipt):
        self._append({'id': call, 'settled_usd': str(cost), 'receipt': receipt, 'at': time.time()})


class StructuredModel:
    """One model, one strict JSON schema per call. Capability gaps fail before any money is reserved."""

    def __init__(self, model, max_tokens=32768, effort='medium', transport=None):
        self.model, self.max_tokens, self.effort, self.transport = model, max_tokens, effort, transport
        self._meta = None

    def _request(self, method, path, body=None):
        if self.transport:
            return self.transport(method, path, body)
        key = os.environ.get('OPENROUTER_API_KEY', '')
        if not key:
            raise ValueError('OPENROUTER_API_KEY fehlt')
        with httpx.Client(timeout=300, follow_redirects=False) as client:
            response = client.request(method, API + path, headers={'Authorization': 'Bearer ' + key}, json=body)
            response.raise_for_status()
            return response.json()

    def meta(self):
        if self._meta is None:
            meta = next((m for m in self._request('GET', '/models')['data'] if m['id'] == self.model), None)
            if not meta:
                raise ValueError(f'{self.model} nicht im Livekatalog')
            params = set(meta.get('supported_parameters', []))
            if not {'structured_outputs', 'response_format', 'max_tokens'} <= params:
                raise ValueError(f'{self.model} erzwingt kein JSON-Schema (structured_outputs fehlt)')
            if self.effort and self.effort not in meta.get('reasoning', {}).get('supported_efforts', []):
                raise ValueError(f'{self.model} unterstützt reasoning_effort={self.effort} nicht')
            self._meta = meta
        return self._meta

    def estimate(self, prompt, images):
        pricing = self.meta()['pricing']
        rate_in = max(Decimal(str(pricing.get('prompt') or 0)), Decimal(str(pricing.get('image') or 0)))
        tokens_in = len(prompt) // PROMPT_CHARS_PER_TOKEN + IMAGE_TOKENS * len(images)
        return (rate_in * tokens_in + Decimal(str(pricing.get('completion') or 0)) * self.max_tokens) * ESTIMATE_MARGIN

    def complete(self, ledger, role, prompt, schema, images=None):
        images = images or {}
        meta = self.meta()
        if images and 'image' not in meta['architecture']['input_modalities']:
            raise ValueError(f'{self.model} kann keine Bilder sehen')
        wire = strict_schema(schema)
        assert_wire_schema(wire)
        content = [{'type': 'text', 'text': prompt}]
        for name, raw in sorted(images.items()):
            content += [{'type': 'text', 'text': 'image_id=' + name},
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(raw).decode()}}]
        body = {'model': self.model, 'messages': [{'role': 'user', 'content': content}], 'temperature': 0, 'max_tokens': self.max_tokens,
                'response_format': {'type': 'json_schema', 'json_schema': {'name': schema.get('title', 'output'), 'strict': True, 'schema': wire}}}
        if self.effort:
            body['reasoning'] = {'effort': self.effort}
        call = ledger.reserve(role, self.estimate(prompt, images))
        response = self._request('POST', '/chat/completions', body)
        cost = (response.get('usage') or {}).get('cost')
        if cost is not None:
            ledger.settle(call, Decimal(str(cost)), digest(canonical(response)))
        choice = (response.get('choices') or [{}])[0]
        if response.get('model') != self.model:
            raise ValueError('Antwort von fremdem Modell')
        if unbilled_error(response):
            raise ValueError('Anbieterfehler ohne Abrechnung')
        if choice.get('finish_reason') != 'stop':
            raise ValueError(f"Antwort unvollständig (finish_reason={choice.get('finish_reason')})")
        return json.loads(choice['message']['content']), response
