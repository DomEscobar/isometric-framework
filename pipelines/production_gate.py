"""Fail-closed production gate. Model decisions are never inferred or rewritten."""
from typing import Literal, Annotated
from pydantic import Field
from style_specs import Strict

CriterionName=Literal['layout_fidelity','materials','pixel_style','walkable_clearance']
CRITERIA=('layout_fidelity','materials','pixel_style','walkable_clearance')
class Observation(Strict):
    observation: str=Field(min_length=20,max_length=1600)
    location: str=Field(min_length=3,max_length=300)
    evidence_ids: list[str]=Field(min_length=1,max_length=20)
class Criterion(Strict):
    verdict: Literal['pass','fail','uncertain']
    observations: list[Observation]=Field(min_length=1,max_length=12)
class Finding(Observation):
    criterion: CriterionName
    correction: str=Field(min_length=10,max_length=1600)
    blocking: bool
class Decision(Strict):
    criteria: dict[CriterionName,Criterion]
    findings: list[Finding]=Field(max_length=32)

def assess(decision,evidence_ids,local_blockers):
    reasons=list(local_blockers)
    result={'criteria':{},'findings':[]}
    try:
        parsed=Decision.model_validate(decision)
        result=parsed.model_dump()
        if set(parsed.criteria)!=set(CRITERIA):raise ValueError('all four criteria required')
        for name,c in parsed.criteria.items():
            cited={e for o in c.observations for e in o.evidence_ids}
            if not cited.issubset(evidence_ids):reasons.append(name+': unknown visible evidence citation')
            if 'final' not in cited:reasons.append(name+': missing final evidence citation')
            if name in ('layout_fidelity','walkable_clearance') and 'guide' not in cited:reasons.append(name+': missing guide citation')
            if name in ('materials','pixel_style') and not any(e.startswith('reference-') for e in cited):reasons.append(name+': missing style reference citation')
            if c.verdict!='pass':reasons.append(name+': '+c.verdict)
        for f in parsed.findings:
            if not set(f.evidence_ids).issubset(evidence_ids):reasons.append(f.criterion+': unknown finding evidence')
            if f.blocking:reasons.append(f.criterion+': blocking model finding')
        result=parsed.model_dump()
    except (ValueError,TypeError):
        reasons.append('invalid/missing structured model decision or applicable citations')
    return dict(**result,production_approved=not reasons,aggregate='pass' if not reasons else 'blocked',blockers=reasons,user_acceptance='pending; not implied by automated gate')
