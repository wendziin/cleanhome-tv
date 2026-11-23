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
- **Escurecimento ajustável**: um controle no painel escurece o papel de parede para os
  ícones e o relógio aparecerem melhor. É uma camada de tinta por cima da imagem — nenhum
  pixel a mais na memória e nenhum reprocessamento, então continua leve.
- **Cópia local dos wallpapers**: cada imagem enviada pelo painel é baixada uma vez e
guardada no próprio app (IndexedDB). O wallpaper escolhido continua na tela com o celular
desligado, fora da rede ou depois de reiniciar a TV, e as miniaturas continuam funcionando.
- **Restauração no boot**: o wallpaper escolhido volta depois de desligar e ligar a TV.
- **Limite de armazenamento**: a TV guarda só os 3 wallpapers mais recentes enviados —
  online no painel e offline na cópia local; ao enviar o quarto, o mais antigo sai da TV.
  Os 8 wallpapers padrão são fixos.
- Upload de JPG, PNG e WebP até 30 MB, validado pelos primeiros bytes do arquivo.

## Estrutura do repositório

```
CleanHome/
├── config.xml          # manifesto Tizen (pacote tvunlock02, perfil tv)
├── config.example.js   # modelo de config.js (o config.js real é pessoal e não versionado)
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

- **Escurecimento** — arraste o controle para deixar o fundo mais escuro (0 a 60%).
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
| POST | `/api/dim` | `{"value": 0..60}` — escurecimento do wallpaper em % |
| POST | `/api/delete` | `{"id": "..."}` — remove o wallpaper |

## Configuração do app

`config.js` é pessoal e **não é versionado** (está no `.gitignore`) — copie o modelo na
primeira vez:

```bash
cp config.example.js config.js
```

```js
window.TV_CONFIG = {
  panelUrl: "http://IP_DO_CELULAR:8099",  // "" desativa a sincronização
  debugUrl: "",                           // coletor de diagnóstico da TV (opcional)

  // Clima sob a data (null desativa). Coordenadas, não nome de cidade.
  weather: { latitude: -23.5505, longitude: -46.6333, units: "celsius" },

  customWallpapers: []                    // wallpapers extras por URL
};
```

- **`panelUrl`** é só o primeiro palpite. Se o app não responder nesse endereço, ele varre
  a sub-rede `/24` na porta do painel, valida com `/health` e guarda o endereço encontrado
  no armazenamento local da TV (nova varredura no máximo a cada 15 minutos).
- **`weather`** é um objeto com `latitude`, `longitude` e `units` (`"celsius"` ou
  `"fahrenheit"`). Os dados vêm da Open-Meteo, que não pede chave. Um texto como
  `"Cidade,UF"` **não** funciona: sem latitude/longitude o bloco de clima fica oculto.
- **`customWallpapers`** aceita `{ id, name, file }` com URL de imagem ou vídeo.

### Como a sincronização funciona

O painel mantém um `revision` que aumenta a cada mudança. O app busca `/config.json` no
boot, ao voltar ao primeiro plano e a cada 60 segundos — mas só aplica o `active` quando a
revisão é maior que a última vista. Assim, uma troca feita pelo controle remoto na TV não
é desfeita pela sincronização.

O **escurecimento** é o único ajuste que não passa pela revisão: ele vale a cada busca e
só muda o fundo da camada `#wallpaper-dim` quando o valor é diferente do atual. Por isso
ajustar o brilho não recarrega o wallpaper nem causa piscada na tela.

## Limitações conhecidas

- **Trocar de app fecha o launcher?** A TV pausa qualquer app quando outro é aberto e pode
  encerrá-lo se faltar memória; não existe API para um app web "ficar fixo na RAM". O que o
  app garante é a volta idêntica: o wallpaper escolhido é restaurado no boot e o painel é
  re-sincronizado ao retornar ao primeiro plano.
- O botão **Home** continua abrindo o Smart Hub da Samsung — assumir o botão Home exige
  mexer em configurações internas da TV, o que este projeto não faz.
- A primeira sincronização ainda precisa do painel ligado: é quando a TV baixa a cópia
  local de cada imagem. Depois disso, desligar o celular não afeta o wallpaper ativo nem
  as miniaturas; só enviar um wallpaper novo exige o painel de volta.
- O painel não tem autenticação; use em rede local confiável.

## Publicar no GitHub (espelho)

Este repositório é um espelho independente — não é um fork. O histórico local é próprio e
começa do zero, sem vínculo com o repositório de origem.

1. Crie um repositório **vazio** no GitHub (sem README, sem `.gitignore`, sem licença).
2. Aponte o remoto e envie:

```bash
cd ~/CleanHome
git remote add origin https://github.com/SEU_USUARIO/cleanhome.git
git push -u origin main
```

Como o repositório remoto já nasce vazio, o `push` é aceito direto — sem `--force`.

### O que não vai para o GitHub

| Fica de fora | Por quê |
| :--- | :--- |
| `config.js` | IP do painel e wallpapers pessoais (modelo: `config.example.js`) |
| `panel/data/` | wallpapers enviados e o estado do painel |
| `*.wgt`, `*.tpk` | builds gerados a partir do código |
| `panel/__pycache__/` | cache do Python |

Confira antes de enviar:

```bash
git ls-files | grep -E "config\.js$|panel/data|wgt" || echo "nada pessoal versionado"
git log -p | grep -nE "([0-9]{1,3}\.){3}[0-9]{1,3}" | head
```

## Créditos

Baseado no launcher Clean Home para TVs Tizen. A interface foi traduzida para PT-BR e
recebeu o painel de wallpapers deste repositório. Este é um espelho independente, mantido
sem vínculo com o projeto de origem.

## Licença

MIT — veja `LICENSE`. O projeto de origem pode ter a sua própria licença; verifique antes
de redistribuir partes dele.
