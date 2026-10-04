DO $avan$
DECLARE
    v_realm text;
    v_flow text;
    v_otp_flow text;
BEGIN
    SELECT id INTO v_realm FROM realm WHERE name='avan';
    IF v_realm IS NULL THEN
        RAISE NOTICE 'AVAN realm does not exist yet; flow provisioning deferred.';
        RETURN;
    END IF;

    SELECT id INTO v_flow
      FROM authentication_flow
     WHERE realm_id=v_realm AND alias='avan-browser'
     ORDER BY id
     LIMIT 1;

    IF v_flow IS NULL THEN
        v_flow := gen_random_uuid()::text;
        INSERT INTO authentication_flow
            (id, realm_id, alias, provider_id, description, top_level, built_in)
        VALUES
            (v_flow, v_realm, 'avan-browser', 'basic-flow',
             'AVAN protected password and conditional second factor', true, false);
    ELSE
        UPDATE authentication_flow
           SET provider_id='basic-flow',
               description='AVAN protected password and conditional second factor',
               top_level=true,
               built_in=false
         WHERE id=v_flow;
    END IF;

    -- Existing installations may contain the stock username/password form under
    -- the AVAN flow. Replace it with the AVAN anti-bot form so the login theme
    -- always receives a real challenge and server-side verification.
    UPDATE authentication_execution
       SET authenticator='avan-captcha-password',
           requirement=0,
           priority=10,
           authenticator_flow=false,
           auth_flow_id=NULL
     WHERE realm_id=v_realm
       AND flow_id=v_flow
       AND authenticator IN ('auth-username-password-form','username-password-form');

    IF NOT EXISTS (
        SELECT 1 FROM authentication_execution
         WHERE realm_id=v_realm
           AND flow_id=v_flow
           AND authenticator='avan-captcha-password'
           AND authenticator_flow=false
    ) THEN
        INSERT INTO authentication_execution
            (id, realm_id, flow_id, authenticator, auth_config, auth_flow_id,
             requirement, priority, authenticator_flow)
        VALUES
            (gen_random_uuid()::text, v_realm, v_flow, 'avan-captcha-password',
             NULL, NULL, 0, 10, false);
    ELSE
        UPDATE authentication_execution
           SET requirement=0, priority=10, authenticator_flow=false, auth_flow_id=NULL
         WHERE realm_id=v_realm
           AND flow_id=v_flow
           AND authenticator='avan-captcha-password';
    END IF;

    SELECT af.id INTO v_otp_flow
      FROM authentication_flow af
      JOIN authentication_execution ae ON ae.auth_flow_id=af.id
     WHERE ae.realm_id=v_realm
       AND ae.flow_id=v_flow
       AND ae.authenticator_flow=true
       AND af.alias='avan-conditional-otp'
     ORDER BY af.id
     LIMIT 1;

    IF v_otp_flow IS NULL THEN
        SELECT id INTO v_otp_flow
          FROM authentication_flow
         WHERE realm_id=v_realm AND alias='avan-conditional-otp'
         ORDER BY id
         LIMIT 1;
    END IF;

    IF v_otp_flow IS NULL THEN
        v_otp_flow := gen_random_uuid()::text;
        INSERT INTO authentication_flow
            (id, realm_id, alias, provider_id, description, top_level, built_in)
        VALUES
            (v_otp_flow, v_realm, 'avan-conditional-otp', 'basic-flow',
             'Ask for OTP only for accounts with OTP credential', false, false);
    ELSE
        UPDATE authentication_flow
           SET provider_id='basic-flow',
               description='Ask for OTP only for accounts with OTP credential',
               top_level=false,
               built_in=false
         WHERE id=v_otp_flow;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM authentication_execution
         WHERE realm_id=v_realm AND flow_id=v_flow
           AND authenticator_flow=true AND auth_flow_id=v_otp_flow
    ) THEN
        INSERT INTO authentication_execution
            (id, realm_id, flow_id, authenticator, auth_config, auth_flow_id,
             requirement, priority, authenticator_flow)
        VALUES
            (gen_random_uuid()::text, v_realm, v_flow, NULL, NULL, v_otp_flow,
             1, 20, true);
    ELSE
        UPDATE authentication_execution
           SET requirement=1, priority=20, authenticator=NULL
         WHERE realm_id=v_realm AND flow_id=v_flow
           AND authenticator_flow=true AND auth_flow_id=v_otp_flow;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM authentication_execution
         WHERE realm_id=v_realm AND flow_id=v_otp_flow
           AND authenticator='conditional-user-configured'
    ) THEN
        INSERT INTO authentication_execution
            (id, realm_id, flow_id, authenticator, auth_config, auth_flow_id,
             requirement, priority, authenticator_flow)
        VALUES
            (gen_random_uuid()::text, v_realm, v_otp_flow,
             'conditional-user-configured', NULL, NULL, 0, 10, false);
    ELSE
        UPDATE authentication_execution
           SET requirement=0, priority=10, authenticator_flow=false
         WHERE realm_id=v_realm AND flow_id=v_otp_flow
           AND authenticator='conditional-user-configured';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM authentication_execution
         WHERE realm_id=v_realm AND flow_id=v_otp_flow
           AND authenticator='auth-otp-form'
    ) THEN
        INSERT INTO authentication_execution
            (id, realm_id, flow_id, authenticator, auth_config, auth_flow_id,
             requirement, priority, authenticator_flow)
        VALUES
            (gen_random_uuid()::text, v_realm, v_otp_flow,
             'auth-otp-form', NULL, NULL, 0, 20, false);
    ELSE
        UPDATE authentication_execution
           SET requirement=0, priority=20, authenticator_flow=false
         WHERE realm_id=v_realm AND flow_id=v_otp_flow
           AND authenticator='auth-otp-form';
    END IF;

    UPDATE realm
       SET login_theme='avan',
           browser_flow=v_flow
     WHERE id=v_realm;

    RAISE NOTICE 'AVAN browser flow ensured and bound: %', v_flow;
END
$avan$;

SELECT r.name AS realm,
       r.login_theme,
       af.alias AS browser_flow,
       COUNT(*) FILTER (WHERE ae.authenticator='avan-captcha-password') AS captcha_steps
  FROM realm r
  LEFT JOIN authentication_flow af ON af.id=r.browser_flow
  LEFT JOIN authentication_execution ae ON ae.flow_id=af.id
 WHERE r.name='avan'
 GROUP BY r.name,r.login_theme,af.alias;
