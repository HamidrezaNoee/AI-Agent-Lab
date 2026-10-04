FROM maven:3.9.11-eclipse-temurin-21 AS builder
WORKDIR /build
COPY infra/keycloak/captcha/pom.xml pom.xml
COPY infra/keycloak/captcha/src src
RUN mvn -q -B -DskipTests package

FROM quay.io/keycloak/keycloak:26.7.3
COPY --from=builder /build/target/avan-captcha-login-1.0.0.jar /opt/keycloak/providers/avan-captcha-login.jar
COPY infra/keycloak/themes/avan /opt/keycloak/themes/avan
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true --spi-theme-selector--provider-default=avan
