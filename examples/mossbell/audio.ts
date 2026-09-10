import type { Cell } from '../../src/index';
import type { World } from './scene';

/** Original procedural audio. No recordings, provider keys or external requests. */
export class Soundscape {
  private ctx?: AudioContext;
  private master?: GainNode;
  private ambient?: GainNode;
  private effects?: GainNode;
  private wind?: GainNode;
  private stream?: GainNode;
  private drone?: GainNode;
  private pan?: StereoPannerNode;
  private analyser?: AnalyserNode;
  private noise?: AudioBuffer;
  private sources: AudioScheduledSourceNode[] = [];
  private world?: World;
  private muted = true;
  private paused = false;
  private hidden = false;
  private disposed = false;
  private ambienceLevel = .65;
  private effectsLevel = .7;
  private nextBird = 7;
  private nextBell = 11;
  private lastFootstep = -1;
  private time = 0;
  private birdCount = 0;
  private events: { kind: string; time: number }[] = [];

  async toggle(): Promise<boolean> {
    if(this.disposed) return false;
    if(!this.ctx) this.init();
    this.muted=!this.muted;
    await this.sync();
    return !this.muted;
  }
  private init() {
    const ctx=this.ctx=new AudioContext();
    this.master=ctx.createGain(); this.master.gain.value=0;
    this.ambient=ctx.createGain(); this.effects=ctx.createGain();
    this.ambient.gain.value=this.ambienceLevel; this.effects.gain.value=this.effectsLevel;
    this.ambient.connect(this.master); this.effects.connect(this.master);
    this.analyser=ctx.createAnalyser(); this.analyser.fftSize=1024;
    this.master.connect(this.analyser); this.analyser.connect(ctx.destination);
    // A long cyclic noise source is window-independent; filtering removes harsh highs.
    const noise=this.noise=ctx.createBuffer(1,ctx.sampleRate*12,ctx.sampleRate), samples=noise.getChannelData(0);
    let seed=4175, brown=0;
    for(let i=0;i<samples.length;i++){seed=(seed*1664525+1013904223)>>>0; brown=(brown+(seed/4294967296*2-1)*.025)/1.015; samples[i]=brown*4;}
    const makeNoise=(frequency:number,gain:number)=>{
      const source=ctx.createBufferSource();source.buffer=noise;source.loop=true;
      const filter=ctx.createBiquadFilter();filter.type='lowpass';filter.frequency.value=frequency;
      const volume=ctx.createGain();volume.gain.value=gain;
      source.connect(filter);filter.connect(volume);source.start();this.sources.push(source);return volume;
    };
    this.wind=makeNoise(650,.15);this.wind.connect(this.ambient);
    this.stream=makeNoise(2100,.1);this.pan=ctx.createStereoPanner();this.stream.connect(this.pan);this.pan.connect(this.ambient);
    this.drone=ctx.createGain();this.drone.gain.value=.008;this.drone.connect(this.ambient);
    for(const frequency of [146.83,220,293.66]) {
      const oscillator=ctx.createOscillator();oscillator.type='sine';oscillator.frequency.value=frequency;
      oscillator.connect(this.drone);oscillator.start();this.sources.push(oscillator);
    }
    if(this.world) this.setWorld(this.world);
  }
  private async sync() {
    const ctx=this.ctx;if(!ctx||!this.master||this.disposed)return;
    const silent=this.muted||this.paused||this.hidden;
    this.master.gain.cancelScheduledValues(ctx.currentTime);
    this.master.gain.setTargetAtTime(silent?0:.65,ctx.currentTime,.08);
    if(this.paused||this.hidden) await ctx.suspend();
    else if(!this.muted) await ctx.resume();
  }
  setPaused(value:boolean){this.paused=value;void this.sync();}
  setHidden(value:boolean){this.hidden=value;void this.sync();}
  levels(ambience:number,effects:number){
    this.ambienceLevel=ambience;this.effectsLevel=effects;
    if(this.ctx){this.ambient?.gain.setTargetAtTime(ambience,this.ctx.currentTime,.1);this.effects?.gain.setTargetAtTime(effects,this.ctx.currentTime,.1);}
  }
  setWorld(world:World){
    this.world=world;this.nextBird=this.time+5;this.nextBell=this.time+9;
    if(this.ctx){const now=this.ctx.currentTime;this.wind?.gain.setTargetAtTime(world.region==='forest'?.25:.12,now,1.5);this.drone?.gain.setTargetAtTime(world.region==='forest'?.012:.005,now,2);}
  }
  private tone(frequency:number,duration:number,volume:number,kind:string,pan=0,to=frequency){
    const ctx=this.ctx;if(!ctx||!this.effects||this.muted||this.paused||this.hidden||this.disposed)return;
    const oscillator=ctx.createOscillator(),gain=ctx.createGain(),stereo=ctx.createStereoPanner();
    const now=ctx.currentTime;oscillator.type='sine';oscillator.frequency.setValueAtTime(frequency,now);oscillator.frequency.exponentialRampToValueAtTime(to,now+duration);
    gain.gain.setValueAtTime(.0001,now);gain.gain.exponentialRampToValueAtTime(Math.max(.0001,volume),now+.015);gain.gain.exponentialRampToValueAtTime(.0001,now+duration);
    stereo.pan.value=Math.max(-1,Math.min(1,pan));oscillator.connect(gain);gain.connect(stereo);stereo.connect(this.effects);
    this.sources.push(oscillator);oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();stereo.disconnect();this.sources=this.sources.filter(s=>s!==oscillator);};
    oscillator.start();oscillator.stop(now+duration+.02);
    this.events.push({kind,time:this.time});if(this.events.length>40)this.events.shift();
  }
  chime(){for(const [i,f] of [587.33,739.99,880,1174.66].entries())this.tone(f,1.8+i*.3,.035,'spring',i%2?.2:-.2);}
  footstep(cell:Cell,surface:string){
    if(this.time-this.lastFootstep<.22)return;this.lastFootstep=this.time;
    const wood=surface==='log',stone=cell.level==='bridge'||surface.startsWith('path')||surface==='stair';
    this.tone(wood?170:stone?360:100,.075,wood?.025:stone?.019:.012,wood?'wood-step':stone?'stone-step':'grass-step',0,wood?75:stone?90:50);
    const ctx=this.ctx;if(!ctx||!this.noise||!this.effects||this.muted||this.paused||this.hidden)return;
    const source=ctx.createBufferSource(),filter=ctx.createBiquadFilter(),gain=ctx.createGain();source.buffer=this.noise;filter.type='highpass';filter.frequency.value=stone?650:wood?300:1100;
    const now=ctx.currentTime;gain.gain.setValueAtTime(.035,now);gain.gain.exponentialRampToValueAtTime(.0001,now+.12);source.connect(filter);filter.connect(gain);gain.connect(this.effects);this.sources.push(source);source.onended=()=>{source.disconnect();filter.disconnect();gain.disconnect();this.sources=this.sources.filter(s=>s!==source);};source.start(now,(this.time*3)%10);source.stop(now+.14);
  }
  step(dt:number,player:Cell){
    this.time+=dt;const world=this.world;if(!world)return;
    if(this.ctx&&this.stream&&this.pan){
      const row=world.region==='town'?14.5:15.5,dist=Math.abs(player.r-row);
      this.stream.gain.setTargetAtTime(.025+.22/(1+dist*.6),this.ctx.currentTime,.4);
      this.pan.pan.setTargetAtTime(Math.max(-.7,Math.min(.7,(row-player.r)*.1)),this.ctx.currentTime,.4);
      if(world.spring&&this.drone){const d=Math.hypot(player.c-world.spring.c,player.r-world.spring.r);this.drone.gain.setTargetAtTime(.006+.045/(1+d*.7),this.ctx.currentTime,.5);}
    }
    if(this.time>this.nextBird){
      this.birdCount++;this.nextBird=this.time+8+(this.birdCount*7%11);
      if(world.region==='forest'){this.tone(460,.55,.024,'owl',-.5,350);this.tone(2800,.13,.012,'insect',.6,3100);}
      else this.tone(1800,.16,.012,'bird',.45,1300);
    }
    if(this.time>this.nextBell){
      this.nextBell=this.time+17;const bell=world.bells[0];if(bell){const d=Math.hypot(player.c-bell.cell.c,player.r-bell.cell.r);this.tone(880,2.6,.12/(1+d),'bell',-.2);this.tone(1321,1.7,.035/(1+d),'bell-partial',-.2);}
    }
  }
  snapshot(){
    let rms=0;if(this.analyser){const data=new Float32Array(this.analyser.fftSize);this.analyser.getFloatTimeDomainData(data);rms=Math.sqrt(data.reduce((a,v)=>a+v*v,0)/data.length);}
    return {enabled:!!this.ctx&&!this.muted,state:this.ctx?.state??'uninitialized',muted:this.muted,paused:this.paused,hidden:this.hidden,ambience:this.ambienceLevel,effects:this.effectsLevel,rms,streamGain:this.stream?.gain.value??0,events:[...this.events],sourceCount:this.sources.length};
  }
  /** Authoring capture of the actual Web Audio mix; same mix reaches speakers. */
  capture(seconds=8):Promise<Blob>{
    if(!this.ctx||!this.master) return Promise.reject(new Error('Enable sound first'));
    const destination=this.ctx.createMediaStreamDestination();this.master.connect(destination);
    const recorder=new MediaRecorder(destination.stream),chunks:BlobPart[]=[];
    return new Promise((resolve,reject)=>{recorder.ondataavailable=e=>chunks.push(e.data);recorder.onerror=()=>reject(new Error('Audio recording failed'));recorder.onstop=()=>{this.master?.disconnect(destination);destination.stream.getTracks().forEach(t=>t.stop());resolve(new Blob(chunks,{type:recorder.mimeType}));};recorder.start();setTimeout(()=>{if(recorder.state!=='inactive')recorder.stop();},seconds*1000);});
  }
  destroy(){this.disposed=true;for(const source of this.sources){try{source.stop();source.disconnect();}catch{ /* already ended */ }}this.sources=[];void this.ctx?.close();}
}
