/* Modelo: copie para config.js e preencha. config.js não é versionado. */
window.TV_CONFIG = {
  // Endereço do painel de wallpapers na rede local (vazio desativa a sincronização)
  panelUrl: "http://IP_DO_CELULAR:8099",

  // Coletor opcional de diagnóstico da TV (recebe /perf, /caps e /dump). Vazio desativa.
  debugUrl: "",

  // Música: app Spotify Connect rodando na mesma rede local
  spotifyUrl: "",
  spotifyClientId: "SEU_CLIENT_ID_DO_SPOTIFY",
  spotifyRefreshToken: "SEU_REFRESH_TOKEN_DO_SPOTIFY",

  // Clima no cabeçalho (null desativa)
  weather: { latitude: -23.5505, longitude: -46.6333, units: "celsius" },

  // Wallpapers extras: { id, name, file }
  customWallpapers: []
};
