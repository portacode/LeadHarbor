/* First-party, consent-aware telemetry. Never inspect form values or text nodes. */
(() => {
  'use strict';
  const mode = document.body.dataset.analyticsMode;
  const cookie = name => document.cookie.split('; ').find(v => v.startsWith(name + '='))?.split('=').slice(1).join('=') || '';
  const optedOut = navigator.globalPrivacyControl || navigator.doNotTrack === '1';
  let enabled = false, queue = [], interacted = false, started = false, maxScroll = 0, beats = 0, inFlight = false;
  let activeMs = 0, lastTick = performance.now();
  const banner = document.getElementById('consent-banner');
  const context = {language:navigator.language, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone};
  const params = new URLSearchParams(location.search);
  for (const key of ['utm_source','utm_medium','utm_campaign']) context[key] = (params.get(key) || '').slice(0,200);
  function event(name, properties = {}) {
    if (!enabled || queue.length >= 40) return;
    queue.push({event:name, path:location.pathname, referrer:document.referrer, context, properties});
  }
  async function flush() {
    if (!enabled || !queue.length || inFlight) return;
    inFlight = true;
    const batch = queue.splice(0,20);
    try {
      await fetch('/api/v1/events/', {method:'POST', credentials:'same-origin', keepalive:true,
        headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(cookie('csrftoken'))}, body:JSON.stringify(batch)});
    } catch (_) { /* Analytics must never interrupt a conversion. */ }
    finally { inFlight = false; }
  }
  function activate() {
    if (enabled || mode === 'off' || optedOut) return;
    enabled = true;
    event('page_load', {viewport_width:innerWidth, viewport_height:innerHeight});
    flush();
  }
  function choose(allow) {
    document.cookie = `analytics_consent=${allow ? 'yes':'no'}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === 'https:' ? '; Secure':''}`;
    banner.hidden = true;
    if (allow) activate();
    else { enabled = false; queue = []; fetch('/api/v1/forget-journey/', {method:'POST',headers:{'X-CSRFToken':decodeURIComponent(cookie('csrftoken'))}}).catch(()=>{}); }
  }
  document.getElementById('accept-analytics')?.addEventListener('click',()=>choose(true));
  document.getElementById('decline-analytics')?.addEventListener('click',()=>choose(false));
  document.getElementById('privacy-settings')?.addEventListener('click',()=>{banner.hidden=false;});
  if (cookie('analytics_consent') !== 'no' && (mode === 'essential' || cookie('analytics_consent') === 'yes')) activate();
  else if (mode === 'consent' && !cookie('analytics_consent') && !optedOut) banner.hidden = false;
  function human(e) {
    if (!enabled || interacted || !e.isTrusted) return;
    interacted = true;
    event('human_detected', {interaction_type:e.type, time_to_interaction_ms:Math.round(performance.now())});
  }
  for (const kind of ['pointerdown','keydown','touchstart']) document.addEventListener(kind,human,{passive:true});
  document.addEventListener('click', e => {
    const target = e.target.closest('[data-track]');
    if (!target) return;
    event('cta_click',{cta_name:target.dataset.track});
    if (target.dataset.booking) event('booking_open', {target:target.dataset.track});
    else if (target.matches('a') && target.origin !== location.origin) event('outbound_click', {platform:target.dataset.track});
    flush();
  });
  const form = document.getElementById('conversion-form');
  form?.addEventListener('focusin', () => {if (!started && enabled) {started=true;event('form_start',{form_key:'primary'});flush();}});
  form?.addEventListener('invalid', () => event('form_error',{error_code:'validation'}),true);
  if (document.querySelector('.form-errors')) event('form_error',{error_code:'server_validation'});
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting && enabled) {event('section_view',{section:entry.target.dataset.section});observer.unobserve(entry.target);}
  }), {threshold:.35});
  document.querySelectorAll('[data-section]').forEach(el=>observer.observe(el));
  document.querySelectorAll('[data-track]').forEach(el => {
    let timer;
    el.addEventListener('pointerenter',()=>{timer=setTimeout(()=>event('user_engagement',{signal_type:'hover_significant',target:el.dataset.track}),1400);});
    el.addEventListener('pointerleave',()=>clearTimeout(timer));
  });
  addEventListener('scroll',()=>{maxScroll=Math.max(maxScroll,Math.round(100*(scrollY+innerHeight)/Math.max(innerHeight,document.documentElement.scrollHeight)));},{passive:true});
  document.addEventListener('mouseout', e=>{if (!e.relatedTarget && e.clientY <= 0) event('exit_intent',{scroll_depth:maxScroll});});
  setInterval(()=>{
    const now = performance.now();
    if (!document.hidden && enabled) activeMs += Math.min(now-lastTick,16000);
    lastTick=now;
    if (enabled && !document.hidden) {
      event('heartbeat',{beat_number:++beats,time_on_page_ms:Math.round(activeMs),scroll_depth:maxScroll,interacted});
      if (interacted) event('user_engagement',{signal_type:'active_attention',duration_ms:Math.round(activeMs)});
      flush();
    }
  },15000);
  document.addEventListener('visibilitychange',()=>{if (document.hidden) {event('page_exit',{time_on_page_ms:Math.round(activeMs),scroll_depth:maxScroll});flush();}});
})();
