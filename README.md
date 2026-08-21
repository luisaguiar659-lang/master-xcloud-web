# Master XCloud Web — versão GitHub Pages

Primeira versão web estática baseada no visual e nos fluxos do Master XCloud v1.8.0.

## O que funciona
- Interface responsiva para celular e desktop.
- Tela de acesso demonstrativa.
- Fluxos visuais de Ativar MAC + DNS, Reset + DNS e Excluir MAC.
- Status e simulação de execução no navegador.
- Pode ser hospedado gratuitamente no GitHub Pages.

## Importante
Esta versão é somente frontend. Ela **não envia login, senha, MAC ou M3U para o painel XCloud** e não salva a senha. Isso é intencional: colocar credenciais ou automação real dentro de JavaScript público no GitHub Pages seria inseguro.

A próxima etapa, quando houver backend gratuito/servidor disponível, é conectar esta interface a uma API própria.

## Publicar no GitHub Pages
1. Crie um repositório novo no GitHub (ex.: `master-xcloud-web`).
2. Envie os arquivos desta pasta para a raiz do repositório.
3. No repositório, abra **Settings → Pages**.
4. Em **Build and deployment**, escolha **Deploy from a branch**.
5. Escolha a branch `main` e a pasta `/ (root)`.
6. Salve. O GitHub mostrará o endereço público depois da publicação.

## Teste local
Abra `index.html` diretamente no navegador. Não é necessário instalar dependências.
