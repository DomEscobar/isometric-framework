"""One canonical masked correction integrated with AutoRepair and shared ledger.
No canvas resampling, repaint, composite or fabricated provider response.
"""
import io,json,os
from decimal import Decimal
import numpy as np
from PIL import Image
from artifacts import canonical,digest,png
from terrain import render_original
from generation import Generation
from auto_adapter import Adapter,QUALITY_AUTHORIZATION,is_hash,measure_registration
from constrained_provider import MaskedWaveSpeed,build_edit_mask,preservation_check

STRATEGY='canonical-sidewalk-mask-v1'


def constrained(w):return w.get('continuation',{}).get('mode')=='constrained-mask-recovery'


class ConstrainedAdapter(Adapter):
    def masked_generation(self):
        return Generation(self.g.root,MaskedWaveSpeed(key=self.g.provider.key),self.g.policy)

    def constrained_authorization(self,rid):
        p=json.loads((self.g.root/'constrained-recovery-policy.json').read_bytes())
        if (p.get('enabled') is not True or p.get('parent_run_id')!=rid
            or p.get('authorization_sha256')!=digest(QUALITY_AUTHORIZATION.read_bytes()) or p.get('strategy')!=STRATEGY):
            raise ValueError('constrained recovery authorization closed or drifted')
        return dict(parent_run_id=rid,authorization_sha256=p['authorization_sha256'],strategy=STRATEGY,
                    reason='One supported provider mask from independently registered and validly reviewed original; preserve road and canonical canvas',max_new_attempts=1)

    def constrained_seed(self,w):
        # The current parent's real reviewed registration, not arbitrary operator pixels.
        seeds=[a for a in w['iterations'] if a.get('plan',{}).get('action')=='register' and a.get('review',{}).get('valid') is True]
        if len(seeds)!=1:raise ValueError('unique reviewed registration seed required')
        a=seeds[0]
        return self.continuation_seed({**w,'best_candidate_id':a['candidate_id'],'best_evaluation_id':a['review']['id']})

    def validate(self,w):
        super().validate(w)
        if not constrained(w):return
        link=w['continuation']
        if self.constrained_authorization(link['parent_run_id'])!=link['authorization']:raise ValueError('constrained authority drift')
        if len(w['iterations'])>1:raise ValueError('constrained single attempt exhausted')
        if w['iterations']:
            a=w['iterations'][0]
            # Reconstruct immutable mask/control from seed before every phase.
            control=self.control(w)
            if a['plan']['control']!=control:raise ValueError('constrained source/mask/control drift')
            if a.get('quote_id'):
                b=self.g.get_quote(a['quote_id'])['binding']
                if b.get('constrained',{}).get('control')!=control:raise ValueError('constrained quote/control drift')

    def masked_inputs(self,w):
        proof=w['continuation']['seed_proof'];tid=proof['candidate_id'];r=self.record(tid)
        src=(self.g.root/'terrain'/tid/'source.png').read_bytes()
        if digest(src)!=r['source_sha256']:raise ValueError('constrained source drift')
        raw=png(np.array(render_original(self.load(w['frozen']['revision']),r,src,w['frozen']['density'])))
        if digest(raw)!=proof['output_sha256']:raise ValueError('constrained seed output drift')
        files=self.files(w['frozen']['revision']);guide=files['clean-guide.png']
        terrain=png(np.array(Image.open(io.BytesIO(guide)).convert('RGBA'))[:,:,3])
        mask=build_edit_mask(files['masks/material-sidewalk.png'],terrain)
        if Image.open(io.BytesIO(raw)).size!=(768,408):raise ValueError('constrained canonical frame mismatch')
        refs=[dict(reference_id=tid,role='correction_target',material=None,input_sha256=digest(raw),source_sha256=r['source_sha256'],raw=raw),
              dict(reference_id=digest(mask),role='edit_mask',material=None,input_sha256=digest(mask),source_sha256=digest(guide),raw=mask)]
        return guide,refs

    def control(self,w):
        guide,refs=self.masked_inputs(w)
        return dict(strategy=STRATEGY,model=MaskedWaveSpeed.model_id,mask_sha256=refs[1]['input_sha256'],source_sha256=refs[0]['input_sha256'])

    def plan(self,w):
        if not constrained(w):return super().plan(w)
        e=self.ev.get(w['evaluation_id']);all_findings=[f for f in e['gate']['findings'] if f.get('blocking')]
        findings=[f for f in all_findings if f.get('location') in ('sidewalk paving','planting bed edges adjacent to sidewalk')]
        deferred=[f for f in all_findings if f not in findings]
        if e['gate']['production_approved']:return {'approved':True}
        if not findings:raise ValueError('no actionable masked findings')
        prompt=('Edit ONLY the WHITE mask regions of the supplied isometric pixel-art terrain. '
                'The black masked road, planting interiors, exterior and outer diamond frame must stay EXACTLY unchanged. '
                'Replace the tiny irregular beige sidewalk pavers with broad flat cream/beige rectangular paving slabs, sparse clean straight seams aligned with the existing 2:1 isometric projection. '
                'Remove grass tufts, serrated protrusions and gravel from the white sidewalk right up to its mask boundary; continue clean paving to the planting edges. '
                'Keep the existing pastel palette, flat two/three-tone pixel clusters, fine dark outlines and ground-only visual language. No asphalt recolor, no street change, no extra objects, no projection change, no full-image redesign. '
                'The unchanged intended style specification (text only; this endpoint has no additional reference field) is: '+self.styles.prompt(w['frozen']['style'])+
                '\nActual reviewed defects (road-related recoloring is intentionally excluded from this LOCAL paving-only attempt): '+canonical(findings).decode())
        return dict(action='generate',findings=findings,deferred_findings=deferred,control=self.control(w),prompt=prompt,prompt_sha256=digest(prompt.encode()),
                    strategy_reason='Actual provider mask rather than full-frame prompt reroll; unchanged road and exterior tested byte-for-pixel before review',
                    provider_fields=['prompt','image','mask_image','size'],source_candidate_id=w['latest_candidate_id'],source_evaluation_id=w['evaluation_id'],
                    reference_changes='Registered original is actual image; canonical sidewalk mask is mask_image. Guide and material references remain bound locally, no unsupported reference fields.',
                    requires_semantic_review=True)

    def guard(self,w):
        self.validate(w)
        if self.liability_blockers():raise ValueError('unresolved project liability')
        total=Decimal(str(self.g.policy.get('total_usd','0')))
        if not self.g.policy.get('approved') or not 0<total<=10:raise ValueError('original central USD10 budget required')
        if not self.reviewer.config.enabled:raise ValueError('reviewer disabled')

    def prepare(self,w,a):
        if not constrained(w):return super().prepare(w,a)
        self.guard(w);meta=self.reviewer.preflight();guide,refs=self.masked_inputs(w)
        g=self.masked_generation()
        g.provider.require_output_contract()
        binding=dict(layout_revision=w['frozen']['revision'],guide_sha256=digest(guide),style_spec_id=w['frozen']['style'],
                     style_id=refs[0]['reference_id'],style_sha256=refs[0]['input_sha256'],style_references=[{k:v for k,v in r.items() if k!='raw'} for r in refs],
                     prompt=a['plan']['prompt'],auto_run_id=w['id'],auto_iteration_id=a['id'],correction_candidate_id=w['latest_candidate_id'],
                     constrained=dict(strategy=STRATEGY,size='768*408',control=a['plan']['control'],intended_style_sha256=digest(canonical(self.styles.get(w['frozen']['style'])))))
        q=g.quote(binding)
        reserve=Decimal(meta['pricing']['prompt'])*meta['context_length']+Decimal(meta['pricing']['completion'])*4096
        if Decimal(g.status()['reserved_usd'])+reserve+Decimal(q['reserve_microusd'])/1000000>Decimal(g.policy['total_usd']):raise ValueError('insufficient shared budget for masked image and conservative review')
        a['review_reservation_estimate_usd']=str(reserve);a['preflight_metadata_sha256']=digest(canonical(meta))
        return q

    def submit(self,w,a):
        if not constrained(w):return super().submit(w,a)
        self.guard(w);self.reviewer.preflight();guide,refs=self.masked_inputs(w)
        g=self.masked_generation();g.provider.require_output_contract()
        return g.confirm(a['quote_id'],w['frozen']['revision'],guide,refs[0]['raw'],[refs[1]['raw']])

    def poll(self,w,a):
        if not constrained(w):return super().poll(w,a)
        g=self.masked_generation();j=g.resume(a['job_id'])
        if j['status']=='completed':
            raw=g.provider.download(j['output_url'])
            d=g.root/'constrained-outputs'/j['id'];d.mkdir(parents=True,exist_ok=True)
            path=d/'provider-original.bin'
            try:
                with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            except FileExistsError:
                if path.read_bytes()!=raw:raise ValueError('provider original drift')
            _,refs=self.masked_inputs(w);check=preservation_check(refs[0]['raw'],raw,refs[1]['raw'])
            check.update(provider_original_sha256=digest(raw),provider_format=Image.open(io.BytesIO(raw)).format)
            a['preservation']=check
            if not check['preserved'] or check['provider_format']!='PNG':
                j.update(status='failed',constrained_blocker=check['blocker'] or 'provider_original_not_lossless_png',preservation=check)
                return g.save(j)
            # The original is imported unchanged through the existing service.
            return self.poll_call(a['job_id'])
        return j

    def register(self,w,a):
        if not constrained(w):return super().register(w,a)
        # Exact-canvas inpainting must not get a NEW fitted transform: that would
        # move the supposedly protected road. Identity import + frozen gate only.
        tid=a['candidate_id'];raw=(self.g.root/'terrain'/tid/'source.png').read_bytes()
        guide,refs=self.masked_inputs(w);check=preservation_check(refs[0]['raw'],raw,refs[1]['raw'])
        if not check['preserved']:return {'blocker':check['blocker'],'preservation':check}
        measured=measure_registration(raw,guide)
        if measured.get('blocker'):return measured
        return dict(candidate_id=tid,preservation=check,frame_measurement=measured,applied_transform='identity; provider original unchanged')

    def review(self,w,a):
        if constrained(w):self.guard(w)
        return super().review(w,a)
