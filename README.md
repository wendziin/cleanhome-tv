# Clean Home

Launcher (home screen) leve para TVs Samsung Tizen, em português, com um painel web
para trocar os wallpapers direto do celular — sem editar arquivo, sem recompilar o app.

- **App** (`index.html`, `main.js`, `style.css`): o launcher que roda na TV. Relógio,
  dock de apps, busca, wallpapers e — a partir desta versão — sincronização com o painel.
- **Painel** (`panel/`): servidor Python (só biblioteca padrão) que roda no celular ou em
  qualquer computador da mesma rede, servindo uma página para enviar, escolher e remover
  wallpapers. A TV busca as mudanças sozinha.

## Funcionalidades

- Interface em PT-BR, sem anúncios, feita para controle remoto (setas, OK, Voltar).
- Relógio, saudação, dock de apps instalados na TV com busca, wallpaper com vídeo ou imagem.
- **Wallpaper remoto**: escolher no painel do celular aplica na TV em até 20 segundos.
- **Descoberta automática do painel**: o app varre a rede local e acha o painel sozinho —
  não precisa mexer no código quando o IP do celular muda.
- **Restauração no boot**: o wallpaper escolhido volta depois de desligar e ligar a TV.
- **Limite de armazenamento**: a TV guarda só os 3 wallpapers mais recentes enviados;
  ao enviar o quarto, o mais antigo sai da TV. Os 8 wallpapers padrão são fixos.
- Upload de JPG, PNG e WebP até 30 MB, validado pelos primeiros bytes do arquivo.

## Estrutura do repositório

```
CleanHome/
├── config.xml          # manifesto Tizen (pacote tvunlock02, perfil tv)
├── config.js           # configurações do app (URL do painel, wallpapers extras)
├── config.example.js   # modelo de config.js, sem dados pessoais
├── index.html          # marcação da tela inicial
├── main.js             # lógica do launcher (apps, foco, relógio, wallpapers, painel)
├── style.css           # visual
├── icon.png, icons/, fonts/, wallpapers/   # recursos (8 wallpapers padrão)
├── wallpapers.json     # lista de wallpapers embutidos e extras
└── panel/
    ├── server.py       # servidor do painel (Python 3, sem dependências)
    ├── start.sh        # atalho para iniciar o painel em :8099
    └── public/         # página do painel + miniaturas dos wallpapers padrão
```

## Instalar o app na TV

O app é um Web Application Tizen (`.wgt`) instalado por sideload — nenhum root e nenhuma
alteração de firmware. Requer TV Tizen 3.0+.

1. Gere o pacote (veja abaixo) ou use o `CleanHome.wgt` já compilado.
2. Instale pelo **Apps2Samsung** no celular ou pelo **Tizen Studio** (`sdb connect` + install).
3. Abra **Clean Home** na lista de apps da TV.

### Gerar o `CleanHome.wgt`

O `.wgt` é um ZIP dos arquivos do app — `config.xml` na raiz, sem a pasta `panel/`:

```bash
cd CleanHome
python3 - <<'PY'
import os, zipfile
raiz = "."
ignorar = {".git", "panel", "build"}          # pastas fora do pacote
fora = {".gitignore", "README.md"}             # arquivos só do repositório
with zipfile.ZipFile("../CleanHome.wgt", "w", zipfile.ZIP_DEFLATED) as z:
    for atual, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in ignorar]
        for nome in arquivos:
            if nome.endswith((".wgt", ".tpk")) or nome in fora:
                continue
            caminho = os.path.join(atual, nome)
            z.write(caminho, os.path.relpath(caminho, raiz))
PY
```

## Painel de wallpapers

Roda no celular (Termux), num computador ou em qualquer máquina com Python 3 na mesma
rede da TV. Não usa biblioteca externa, banco de dados nem internet.

```bash
cd CleanHome/panel
./start.sh                 # http://IP_DA_MAQUINA:8099
# opções: --port 8099 --host 0.0.0.0 --keep 3
```

No navegador do celular abra `http://IP_DA_MAQUINA:8099` e:

- **Enviar imagem** (ou arrastar) — a imagem vai para a lista e a TV baixa dela.
- **Tocar numa imagem** — aplica como wallpaper na TV.
- **Remover** — apaga do celular; se estiver ativa na TV, a TV cai para o wallpaper padrão.

O estado fica em `panel/data/` (não versionado): `config.json` com a lista e os arquivos
enviados. Backup = copiar essa pasta.

### API do painel

| Método | Rota | O que faz |
| --- | --- | --- |
| GET | `/` | Página do painel |
| GET | `/health` | `{"ok": true}` — usado pela TV para confirmar que achou o painel |
| GET | `/api/state` | Lista de wallpapers, ativo, revisão e limite (`keep`) |
| GET | `/config.json` | Formato que o app consome (URLs absolutas montadas pelo `Host`) |
| GET | `/wallpapers/<arquivo>` | Imagem enviada |
| GET | `/builtin/<id>.jpg` | Miniatura de um wallpaper padrão |
| POST | `/api/upload?filename=...` | Corpo = bytes da imagem; responde `id`, `evicted`, `keep` |
| POST | `/api/select` | `{"id": "..."}` — torna o wallpaper ativo |
| POST | `/api/delete` | `{"id": "..."}` — remove o wallpaper |

## Configuração do app

`config.js` (copie de `config.example.js` se não existir):

```js
window.TV_CONFIG = {
  weather: null,                          // "Cidade,UF" para mostrar clima
  panelUrl: "http://192.0.2.10:8099",    // "" desativa a sincronização
  customWallpapers: []                    // wallpapers extras por URL
};
```

- **`panelUrl`** é só o primeiro palpite. Se o app não responder nesse endereço, ele varre
  a sub-rede `/24` na porta do painel, valida com `/health` e guarda o endereço encontrado
  no armazenamento local da TV (nova varredura no máximo a cada 5 minutos).
- **`customWallpapers`** aceita `{ id, name, file }` com URL de imagem ou vídeo.

### Como a sincronização funciona

O painel mantém um `revision` que aumenta a cada mudança. O app busca `/config.json` no
boot, ao voltar ao primeiro plano e a cada 20 segundos — mas só aplica o `active` quando a
revisão é maior que a última vista. Assim, uma troca feita pelo controle remoto na TV não
é desfeita pela sincronização.

## Limitações conhecidas

- **Trocar de app fecha o launcher?** A TV pausa qualquer app quando outro é aberto e pode
  encerrá-lo se faltar memória; não existe API para um app web "ficar fixo na RAM". O que o
  app garante é a volta idêntica: o wallpaper escolhido é restaurado no boot e o painel é
  re-sincronizado ao retornar ao primeiro plano.
- O botão **Home** continua abrindo o Smart Hub da Samsung — assumir o botão Home exige
  mexer em configurações internas da TV, o que este projeto não faz.
- A TV baixa os wallpapers do painel: se o celular estiver desligado, a imagem atual
  continua aparecendo, mas trocar de wallpaper e as miniaturas ficam indisponíveis.
- O painel não tem autenticação; use em rede local confiável.

## Publicar no GitHub

O repositório é local; nada é enviado até você rodar o `push`. Para publicar como fork do
projeto original:

```bash
# 1) Faça o fork no GitHub (botão "Fork") e copie a URL do SEU fork.
# 2) Aponte o remoto e envie:
cd ~/CleanHome
git remote add origin https://github.com/SEU_USUARIO/SEU_FORK.git
git push -u origin main
```

O primeiro `push` pode ser recusado porque o histórico local é independente do fork. Como
o conteúdo local já é a versão que você quer publicar, use:

```bash
git push -f -u origin main
```

Isso substitui o conteúdo do fork pelo seu. O vínculo "forked from" continua aparecendo no
GitHub. Se preferir manter o histórico do original:

```bash
git remote add upstream https://github.com/PROJETO_ORIGINAL/CleanHome.git
git fetch upstream
git rebase --onto upstream/main --root main   # resolve os conflitos e segue
git push -u origin main
```

Antes de publicar, confira o que vai junto:

```bash
git status
git ls-files
```

`panel/data/` (seus wallpapers e o estado do painel) e os arquivos `.wgt` ficam fora do
versionamento pelo `.gitignore`. Se você colocou IPs ou links pessoais em `config.js`,
considere voltar para os valores de `config.example.js` no commit.

## Créditos

Baseado no launcher Clean Home para TVs Tizen. A interface foi traduzida para PT-BR e
recebeu o painel de wallpapers deste repositório.

## Licença

Ainda não definida neste repositório. O projeto de origem pode ter a sua própria licença —
verifique antes de redistribuir.
