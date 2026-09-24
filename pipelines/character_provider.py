"""Single static character adapter; reuses Generation's central ledger unchanged."""
from provider import WaveSpeed

class CharacterProvider(WaveSpeed):
    model_id='meta/muse-image/edit'
    requires_size=False
    def input_template(self,binding):
        if binding.get('scope')!='single-static-character-v1':
            raise ValueError('character-specific immutable authorization binding required')
        return {'prompt':binding['prompt'],'image_urls':['https://example.invalid/guide.png','https://example.invalid/style.png'],'output_format':'png','aspect_ratio':'1:1'}
