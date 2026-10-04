package com.avan.identity;

import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.theme.DefaultThemeSelectorProvider;
import org.keycloak.theme.Theme;
import org.keycloak.theme.ThemeSelectorProvider;

/**
 * Forces the AVAN login experience for the AVAN realm even when an older
 * persisted realm record still points at Keycloak's default login theme.
 *
 * All non-login theme types and all other realms delegate to Keycloak's
 * standard selector so the admin/master realm remains untouched.
 */
public final class AvanThemeSelectorProvider implements ThemeSelectorProvider {
    private final KeycloakSession session;
    private final ThemeSelectorProvider delegate;

    public AvanThemeSelectorProvider(KeycloakSession session) {
        this.session = session;
        this.delegate = new DefaultThemeSelectorProvider(session);
    }

    @Override
    public String getThemeName(Theme.Type type) {
        RealmModel realm = session.getContext().getRealm();
        if (type == Theme.Type.LOGIN && realm != null && "avan".equals(realm.getName())) {
            return "avan";
        }
        return delegate.getThemeName(type);
    }

    @Override
    public void close() {
        delegate.close();
    }
}
