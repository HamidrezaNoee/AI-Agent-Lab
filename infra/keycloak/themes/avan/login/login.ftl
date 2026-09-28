<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آوان | ورود</title>
<link rel="stylesheet" href="${url.resourcesPath?html}/css/avan.css"></head>
<body class="avan-signin">
 <main class="signin-layout">
  <section class="signin-panel" aria-labelledby="signin-heading">
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
   <div class="signin-heading"><span class="signin-label">AVAN · AI AGENT</span><h1 id="signin-heading">ورود به فضای کار</h1></div>
   <#if message?has_content && message.type == 'error'><div class="signin-error" role="alert">${message.summary?html}</div></#if>
   <form id="kc-form-login" action="${url.loginAction?html}" method="post" autocomplete="on">
    <label for="username">نام کاربری</label>
    <input id="username" name="username" type="text" value="${(login.username!'')?html}" autocomplete="username" maxlength="256" autofocus required>
    <label for="password">رمز عبور</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required>
    <button id="kc-login" type="submit">ورود به آوان <span aria-hidden="true">←</span></button>
   </form>
  </section>
  <div class="signin-art" aria-hidden="true"></div>
 </main>
</body></html>
