<script lang="ts">
  import { onMount } from 'svelte';
  import type { AdminConfig, AdminPayload, MosaicState } from '$lib/types';
  import '../../app.css';

  let payload = $state<AdminPayload | null>(null);
  let config = $state<AdminConfig | null>(null);
  let mosaic = $state<MosaicState | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let message = $state('');
  let error = $state('');

  onMount(() => {
    void loadConfig();
    void fetch('/api/mosaic')
      .then((response) => response.ok ? response.json() : null)
      .then((data: MosaicState | null) => { if (data) mosaic = data; });

    const events = new EventSource('/api/events');
    events.addEventListener('mosaic', (event) => {
      mosaic = JSON.parse((event as MessageEvent<string>).data) as MosaicState;
    });
    return () => events.close();
  });

  async function loadConfig() {
    loading = true;
    error = '';
    try {
      const response = await fetch('/api/admin/config');
      if (!response.ok) throw new Error('Nie udało się pobrać konfiguracji');
      const data = await response.json() as AdminPayload;
      payload = data;
      config = structuredClone(data.config);
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Błąd połączenia z API';
    } finally {
      loading = false;
    }
  }

  async function saveConfig(event: SubmitEvent) {
    event.preventDefault();
    if (!config) return;
    saving = true;
    message = '';
    error = '';
    try {
      const response = await fetch('/api/admin/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Sprawdź wprowadzone parametry';
        throw new Error(detail);
      }
      payload = data as AdminPayload;
      config = structuredClone((data as AdminPayload).config);
      message = 'Konfiguracja została zapisana i zastosowana.';
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Nie udało się zapisać konfiguracji';
    } finally {
      saving = false;
    }
  }

  function setSourceType(stream: AdminConfig['streams'][number], sourceType: 'local' | 'youtube') {
    stream.source_type = sourceType;
    if (sourceType === 'local') {
      stream.url = '';
      stream.filename ||= payload?.available_videos[0] ?? '';
    } else {
      stream.filename = '';
    }
  }
</script>

<svelte:head><title>Administracja · Mozaika TV</title></svelte:head>

<div class="admin-shell">
  <header class="admin-header">
    <a class="brand" href="/" aria-label="Przejdź do mozaiki">
      <span class="brand-mark"><i></i><i></i><i></i><i></i></span>
      <span><b>MOZAIKA</b><em>TV</em></span>
    </a>
    <div class="header-copy">
      <span>PANEL STEROWANIA</span>
      <strong>Konfiguracja źródeł</strong>
    </div>
    <a class="preview-link" href="/">Podgląd prezentacyjny <span>↗</span></a>
  </header>

  <main class="admin-main">
    <div class="intro">
      <div>
        <span class="eyebrow">SYSTEM / STREAM CONTROL</span>
        <h1>Ustawienia mozaiki</h1>
        <p>Wybierz cztery źródła: pliki lokalne, filmy YouTube lub transmisje YouTube Live. Zapis działa bez restartu aplikacji.</p>
      </div>
      <div class="runtime-status">
        <i class:active={mosaic}></i>
        <span><small>STATUS SILNIKA</small><b>{mosaic ? 'PRACUJE' : 'OCZEKIWANIE'}</b></span>
        <span><small>WERSJA</small><b>#{mosaic?.version?.toString().padStart(4, '0') ?? '0000'}</b></span>
      </div>
    </div>

    {#if loading}
      <section class="loading-card"><span></span> Ładowanie konfiguracji…</section>
    {:else if config && payload}
      <form onsubmit={saveConfig}>
        <section class="settings-card">
          <div class="card-heading">
            <span class="section-number">01</span>
            <div><h2>Parametry przechwytywania</h2><p>Wspólne ustawienia dla wszystkich czterech kafelków.</p></div>
          </div>
          <div class="settings-grid">
            <label>
              <span>Interwał minimalny</span>
              <div class="input-unit"><input type="number" min="1" max="60" step="0.1" bind:value={config.refresh_min_seconds} required /><i>s</i></div>
            </label>
            <label>
              <span>Interwał maksymalny</span>
              <div class="input-unit"><input type="number" min="1" max="60" step="0.1" bind:value={config.refresh_max_seconds} required /><i>s</i></div>
            </label>
            <label>
              <span>Szerokość klatki</span>
              <div class="input-unit"><input type="number" min="320" max="3840" step="2" bind:value={config.frame_width} required /><i>px</i></div>
            </label>
            <label>
              <span>Wysokość klatki</span>
              <div class="input-unit"><input type="number" min="180" max="2160" step="2" bind:value={config.frame_height} required /><i>px</i></div>
            </label>
            <label>
              <span>Jakość WebP</span>
              <div class="input-unit"><input type="number" min="30" max="100" step="1" bind:value={config.webp_quality} required /><i>%</i></div>
            </label>
          </div>
        </section>

        <section class="sources-section">
          <div class="card-heading">
            <span class="section-number">02</span>
            <div><h2>Źródła obrazu</h2><p>Każdy plik lub adres YouTube może zostać przypisany tylko do jednego kafelka.</p></div>
          </div>
          <div class="source-grid">
            {#each config.streams as stream (stream.slot)}
              <article class="source-card">
                <div class="mini-preview">
                  {#if mosaic?.tiles[stream.slot - 1]?.frame_url}
                    <img src={mosaic.tiles[stream.slot - 1].frame_url} alt="" />
                  {:else}
                    <span>NO SIGNAL</span>
                  {/if}
                  <b>0{stream.slot}</b>
                  <i></i>
                </div>
                <div class="source-fields">
                  <label>
                    <span>Typ źródła</span>
                    <select
                      value={stream.source_type}
                      onchange={(event) => setSourceType(
                        stream,
                        event.currentTarget.value as 'local' | 'youtube'
                      )}
                    >
                      <option value="local">Plik lokalny</option>
                      <option value="youtube">YouTube / YouTube Live</option>
                    </select>
                  </label>
                  {#if stream.source_type === 'local'}
                    <label>
                      <span>Plik źródłowy</span>
                      <select bind:value={stream.filename} required>
                        {#each payload.available_videos as filename}
                          <option value={filename}>{filename}</option>
                        {/each}
                      </select>
                    </label>
                  {:else}
                    <label>
                      <span>Adres filmu lub transmisji YouTube</span>
                      <input
                        type="url"
                        placeholder="https://www.youtube.com/watch?v=..."
                        bind:value={stream.url}
                        required
                      />
                    </label>
                  {/if}
                  <label>
                    <span>Nazwa ekranowa</span>
                    <input type="text" minlength="1" maxlength="80" bind:value={stream.title} required />
                  </label>
                </div>
              </article>
            {/each}
          </div>
        </section>

        <div class="action-bar">
          <div aria-live="polite">
            {#if error}<span class="form-error">{error}</span>{/if}
            {#if message}<span class="form-success">{message}</span>{/if}
          </div>
          <button type="submit" disabled={saving}>{saving ? 'ZAPISYWANIE…' : 'ZAPISZ I ZASTOSUJ'}</button>
        </div>
      </form>
    {:else}
      <section class="error-card">
        <strong>Brak połączenia</strong>
        <p>{error || 'Panel nie otrzymał konfiguracji z serwera.'}</p>
        <button type="button" onclick={loadConfig}>Spróbuj ponownie</button>
      </section>
    {/if}
  </main>
</div>

<style>
  :global(body) { overflow: auto; background: #080a0f; }
  .admin-shell { min-height: 100dvh; background: radial-gradient(900px 480px at 75% -10%, rgb(117 140 255 / 10%), transparent 65%), radial-gradient(800px 550px at -10% 70%, rgb(233 255 91 / 5%), transparent 65%), #080a0f; }
  .admin-header { position: sticky; z-index: 20; top: 0; display: grid; grid-template-columns: 1fr auto 1fr; height: 74px; padding: 0 34px; border-bottom: 1px solid var(--line); background: rgb(8 10 15 / 84%); backdrop-filter: blur(20px); }
  .header-copy { display: grid; align-content: center; justify-items: center; gap: 5px; }
  .header-copy span { color: var(--muted); font: 600 8px/1 var(--mono); letter-spacing: .16em; }
  .header-copy strong { font-size: 13px; font-weight: 560; }
  .preview-link { justify-self: end; align-self: center; padding: 10px 13px; border: 1px solid var(--line); border-radius: 9px; color: var(--text); font: 600 10px/1 var(--mono); letter-spacing: .04em; text-decoration: none; transition: border-color 160ms ease, background 160ms ease; }
  .preview-link:hover { border-color: rgb(233 255 91 / 45%); background: rgb(233 255 91 / 5%); }
  .preview-link span { margin-left: 7px; color: var(--accent); }
  .admin-main { display: block; width: min(1340px, calc(100% - 48px)); margin: 0 auto; padding: 52px 0 70px; }
  .intro { display: flex; justify-content: space-between; align-items: end; gap: 30px; margin-bottom: 38px; }
  .eyebrow { color: var(--accent); font: 650 9px/1 var(--mono); letter-spacing: .17em; }
  h1 { margin: 11px 0 9px; font-size: clamp(32px, 4vw, 54px); line-height: .98; font-weight: 590; letter-spacing: -.045em; }
  .intro p { max-width: 620px; margin: 0; color: var(--muted); font-size: 14px; line-height: 1.6; }
  .runtime-status { display: flex; align-items: center; gap: 18px; padding: 15px 18px; border: 1px solid var(--line); border-radius: 13px; background: rgb(255 255 255 / 2%); }
  .runtime-status > i { width: 8px; height: 8px; border-radius: 50%; background: var(--amber); box-shadow: 0 0 12px var(--amber); }
  .runtime-status > i.active { background: var(--green); box-shadow: 0 0 12px var(--green); }
  .runtime-status span { display: grid; gap: 5px; }
  .runtime-status small { color: var(--muted); font: 600 7px/1 var(--mono); letter-spacing: .13em; }
  .runtime-status b { font: 650 10px/1 var(--mono); letter-spacing: .08em; }
  .settings-card, .sources-section, .loading-card, .error-card { border: 1px solid var(--line); border-radius: 18px; background: rgb(14 17 23 / 88%); box-shadow: 0 24px 80px rgb(0 0 0 / 22%); }
  .settings-card { padding: 26px 28px 30px; }
  .sources-section { margin-top: 18px; padding: 26px 28px 28px; }
  .card-heading { display: flex; align-items: start; gap: 14px; margin-bottom: 25px; }
  .section-number { display: grid; place-items: center; width: 30px; height: 27px; border: 1px solid rgb(233 255 91 / 35%); border-radius: 7px; color: var(--accent); font: 650 9px/1 var(--mono); }
  .card-heading h2 { margin: 0 0 5px; font-size: 17px; font-weight: 600; letter-spacing: -.015em; }
  .card-heading p { margin: 0; color: var(--muted); font-size: 11px; }
  .settings-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
  label { display: grid; gap: 8px; }
  label > span { color: #a3aab4; font: 600 9px/1 var(--mono); letter-spacing: .06em; }
  input, select { width: 100%; height: 44px; padding: 0 13px; border: 1px solid rgb(255 255 255 / 10%); border-radius: 9px; outline: none; background: #090b10; color: var(--text); font-size: 12px; transition: border-color 160ms ease, box-shadow 160ms ease; }
  input:focus, select:focus { border-color: rgb(233 255 91 / 60%); box-shadow: 0 0 0 3px rgb(233 255 91 / 7%); }
  .input-unit { position: relative; }
  .input-unit input { padding-right: 38px; }
  .input-unit i { position: absolute; right: 13px; top: 17px; color: var(--muted); font: 600 9px/1 var(--mono); font-style: normal; }
  .source-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .source-card { display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 16px; padding: 12px; border: 1px solid rgb(255 255 255 / 8%); border-radius: 13px; background: rgb(5 7 10 / 55%); }
  .mini-preview { position: relative; min-height: 118px; overflow: hidden; border: 1px solid rgb(255 255 255 / 12%); border-radius: 9px; background: #030405; }
  .mini-preview img { width: 100%; height: 100%; object-fit: cover; }
  .mini-preview span { position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); font: 600 8px/1 var(--mono); letter-spacing: .14em; }
  .mini-preview::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgb(0 0 0 / 18%), transparent 50%, rgb(0 0 0 / 55%)); pointer-events: none; }
  .mini-preview b { position: absolute; z-index: 2; top: 8px; left: 8px; display: grid; place-items: center; width: 27px; height: 24px; border-radius: 6px; background: rgb(0 0 0 / 65%); font: 650 9px/1 var(--mono); }
  .mini-preview i { position: absolute; z-index: 2; right: 9px; bottom: 9px; width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 9px var(--green); }
  .source-fields { display: grid; align-content: center; gap: 14px; }
  .action-bar { position: sticky; z-index: 10; bottom: 14px; display: flex; justify-content: space-between; align-items: center; min-height: 70px; margin-top: 18px; padding: 12px 14px 12px 22px; border: 1px solid rgb(255 255 255 / 13%); border-radius: 15px; background: rgb(13 16 21 / 91%); box-shadow: 0 18px 60px rgb(0 0 0 / 42%); backdrop-filter: blur(20px); }
  .action-bar button, .error-card button { min-width: 205px; height: 46px; border: 0; border-radius: 10px; background: var(--accent); color: #0a0c07; cursor: pointer; font: 750 10px/1 var(--mono); letter-spacing: .08em; }
  .action-bar button:disabled { cursor: wait; opacity: .56; }
  .form-error, .form-success { font: 600 10px/1.35 var(--mono); }
  .form-error { color: var(--red); }
  .form-success { color: var(--green); }
  .loading-card { display: flex; align-items: center; justify-content: center; gap: 13px; min-height: 200px; color: var(--muted); font-size: 12px; }
  .loading-card span { width: 22px; height: 22px; border: 2px solid rgb(255 255 255 / 10%); border-top-color: var(--accent); border-radius: 50%; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error-card { padding: 30px; }
  .error-card p { color: var(--muted); }
  .error-card button { min-width: 160px; }

  @media (max-width: 980px) {
    .settings-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .source-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 700px) {
    .admin-header { grid-template-columns: 1fr auto; height: 66px; padding: 0 16px; }
    .header-copy { display: none; }
    .preview-link { font-size: 0; }
    .preview-link span { margin: 0; font-size: 13px; }
    .admin-main { width: min(100% - 24px, 1340px); padding: 30px 0 55px; }
    .intro { display: grid; }
    .runtime-status { width: 100%; }
    .settings-card, .sources-section { padding: 20px 16px; }
    .settings-grid { grid-template-columns: 1fr; }
    .source-card { grid-template-columns: 1fr; }
    .mini-preview { aspect-ratio: 16 / 9; }
    .action-bar { align-items: stretch; flex-direction: column; gap: 11px; padding: 12px; }
    .action-bar button { width: 100%; }
  }
</style>
