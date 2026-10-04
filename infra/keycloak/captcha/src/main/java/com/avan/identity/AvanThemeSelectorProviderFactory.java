package com.avan.identity;

import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.theme.ThemeSelectorProvider;
import org.keycloak.theme.ThemeSelectorProviderFactory;

/**
 * AVAN theme selector registered as the default Theme Selector SPI provider.
 */
public final class AvanThemeSelectorProviderFactory implements ThemeSelectorProviderFactory {
    public static final String ID = "avan";

    @Override
    public ThemeSelectorProvider create(KeycloakSession session) {
        return new AvanThemeSelectorProvider(session);
    }

    @Override
    public void init(Config.Scope config) {
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {
    }

    @Override
    public void close() {
    }

    @Override
    public String getId() {
        return ID;
    }
}
