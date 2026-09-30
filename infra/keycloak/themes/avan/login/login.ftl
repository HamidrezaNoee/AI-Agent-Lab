<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آوان | ورود</title>
<link rel="stylesheet" href="${url.resourcesPath?html}/css/avan.css">
<script defer src="${url.resourcesPath?html}/js/login-scene.js" data-appearance-url="${url.resourcesPath?html}/generated/appearance.json" data-scene-root="${url.resourcesPath?html}/scene-data/"></script>
<script defer src="${url.resourcesPath?html}/js/login-reveal.js"></script>
<#if antibotChallenge?? || turnstileSiteKey??>
<script defer src="${url.resourcesPath?html}/js/captcha-ui.js"></script>
</#if></head>
<body class="avan-signin">
 <main class="signin-layout">
  <section class="signin-panel login-reveal-card is-collapsed" aria-labelledby="signin-heading">
   <div class="signin-card-decor" aria-hidden="true">
    <svg viewBox="0 0 600 760" preserveAspectRatio="none" focusable="false">
     <defs>
      <linearGradient id="signinStroke" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#79ecff"/><stop offset=".48" stop-color="#16d7f2"/><stop offset="1" stop-color="#0b8fff"/></linearGradient>
      <radialGradient id="signinGlow"><stop offset="0" stop-color="#35ecff" stop-opacity=".9"/><stop offset="1" stop-color="#35ecff" stop-opacity="0"/></radialGradient>
      <pattern id="signinDots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.35" fill="#1fdcf4" opacity=".5"/></pattern>
     </defs>
     <rect x="1.5" y="1.5" width="597" height="757" rx="34" fill="none" stroke="url(#signinStroke)" stroke-width="2"/>
     <path d="M0 178C78 129 111 75 155 0" fill="none" stroke="#18cffa" stroke-width="1.25" opacity=".8"/>
     <path d="M600 546C537 592 522 691 425 760" fill="none" stroke="#18cffa" stroke-width="1.25" opacity=".8"/>
     <path d="M0 105C70 72 91 41 119 0" fill="none" stroke="#178fd8" stroke-width=".7" opacity=".65"/>
     <path d="M600 623C558 653 540 705 486 760" fill="none" stroke="#178fd8" stroke-width=".7" opacity=".65"/>
     <rect x="34" y="62" width="128" height="146" fill="url(#signinDots)" opacity=".38"/>
     <rect x="444" y="568" width="118" height="118" fill="url(#signinDots)" opacity=".3"/>
     <circle cx="301" cy="2" r="42" fill="url(#signinGlow)" opacity=".42"/>
    </svg>
   </div>
   <div class="signin-brand"><span class="signin-mark" aria-hidden="true"><svg viewBox="0 0 64 64" focusable="false"><defs><linearGradient id="signinMarkGradient" x1="8" y1="7" x2="55" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#24f0e0"/><stop offset=".48" stop-color="#10cbe8"/><stop offset="1" stop-color="#1689ff"/></linearGradient></defs><path d="M30.9 7.7c1.7-3 6-3 7.7 0l18 31.2c1.8 3.1-.4 7-4 7H39.1L32 33.6l-7.1 12.3H11.4c-3.6 0-5.8-3.9-4-7l18-31.2c1.2-2 4.2-2 5.5 0Z" fill="url(#signinMarkGradient)"/><path d="M32 33.6 39.1 46H24.9L32 33.6Z" fill="#08263b"/></svg></span><span class="signin-brand-copy"><strong>آوان</strong><small>AI AGENT</small></span></div>
   <div class="signin-heading"><span class="signin-label">AVAN · AI AGENT</span><h1 id="signin-heading">ورود به آوان</h1></div>
   <p class="login-reveal-subtitle">خوش آمدید؛ برای ادامه وارد حساب کاربری شوید.</p>
   <button class="login-reveal-toggle" type="button" data-login-reveal aria-expanded="false"><span>ورود</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 9.5 5 5 5-5"></path></svg></button>
   <#if message?has_content && message.type == 'error'><div class="signin-error" role="alert">${message.summary?html}</div></#if>
   <form id="kc-form-login" class="login-expand-body" action="${url.loginAction?html}" method="post" autocomplete="on">
    <label for="username">نام کاربری</label>
    <input id="username" name="username" type="text" value="${(login.username!'')?html}" autocomplete="username" maxlength="256" required>
    <label for="password">رمز عبور</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required>
    <#if antibotChallenge?? || turnstileSiteKey??>
    <div class="avan-captcha is-loading" data-avan-captcha
         data-provider="${(antibotProvider!'altcha-self-hosted')?html}"
         data-action="${(antibotAction!'avan-login')?html}"
         data-site-key="${(turnstileSiteKey!'')?html}"
         data-turnstile-timeout="${(turnstileTimeoutMs!2500)?c}"
         data-force-local="${(antibotForceLocal!false)?c}"
         data-algorithm="${(antibotAlgorithm!'')?html}"
         data-challenge="${(antibotChallenge!'')?html}"
         data-salt="${(antibotSalt!'')?html}"
         data-signature="${(antibotSignature!'')?html}"
         data-max-number="${(antibotMaxNumber!0)?c}"
         data-expires-in="${(antibotExpiresIn!120)?c}"
         aria-label="اعتبارسنجی امنیتی">
     <input id="avan-antibot" name="avan-antibot" type="hidden" value="">
     <div class="avan-captcha-head">
      <div class="avan-captcha-visual" aria-hidden="true">
       <span class="captcha-scan-ring ring-a"></span><span class="captcha-scan-ring ring-b"></span>
       <span class="captcha-orbit-dot dot-a"></span><span class="captcha-orbit-dot dot-b"></span>
       <svg class="captcha-shield" viewBox="0 0 64 64" focusable="false">
        <defs><linearGradient id="captchaShieldGradient" x1="10" y1="8" x2="54" y2="57" gradientUnits="userSpaceOnUse"><stop stop-color="#65f6e8"/><stop offset=".52" stop-color="#23d9f1"/><stop offset="1" stop-color="#168cff"/></linearGradient></defs>
        <path class="shield-body" d="M32 5.5 52 13v15.2c0 13.2-7.8 23.8-20 30.3C19.8 52 12 41.4 12 28.2V13l20-7.5Z"></path>
        <path class="shield-scan" d="M20.3 31.8 28 39.5 44.8 22.7"></path>
       </svg>
      </div>
      <div class="avan-captcha-copy"><strong>بررسی امنیتی هوشمند</strong><span class="avan-captcha-status" aria-live="polite">در حال آماده‌سازی Proof-of-Work محلی…</span></div>
      <span class="avan-captcha-badge">HYBRID</span>
     </div>
     <div class="avan-captcha-progress" aria-hidden="true"><span></span></div>
     <div class="avan-captcha-challenge"><span class="captcha-provider">CLOUDFLARE → ALTCHA FALLBACK</span><div class="captcha-turnstile-slot"></div></div>
    </div>
    <#else>
    <div class="avan-captcha is-error" aria-label="سرویس ضدربات در دسترس نیست">
     <div class="avan-captcha-copy"><strong>سرویس امنیتی آماده نیست</strong><span class="avan-captcha-status">کانتینر Anti-Bot آوان را بررسی کنید.</span></div>
    </div>
    </#if>
    <button id="kc-login" type="submit" disabled="disabled">ورود به آوان <span aria-hidden="true">←</span></button>
   </form>
  </section>
  <div class="signin-art" aria-hidden="true"></div>
 </main>
</body></html>
