# Assinatura oficial do MASTER XCLOUD

A partir da versão 0.2.0, o APK release deve ser assinado sempre com a mesma chave.

## GitHub Actions Secrets obrigatórios

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

O workflow `.github/workflows/build-master-xcloud-apk.yml` falha de propósito se algum desses secrets estiver ausente. Isso evita gerar uma versão assinada com uma chave diferente.

## Regra de atualização

Nunca gerar uma nova chave para versões futuras. O mesmo keystore e as mesmas credenciais devem ser preservados para todas as atualizações do aplicativo `com.masterxcloud.app`.

A versão 0.1.0 foi construída como debug. Como a assinatura oficial começa na 0.2.0, pode ser necessário desinstalar a 0.1.0 uma única vez antes de instalar a 0.2.0. Da 0.2.0 em diante, as novas versões poderão ser instaladas por cima, desde que o `versionCode` aumente e a mesma chave seja utilizada.
