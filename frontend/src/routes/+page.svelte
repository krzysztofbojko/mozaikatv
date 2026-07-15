<script lang="ts">
  import { onMount } from 'svelte';
  import Tile from '$lib/Tile.svelte';
  import type { MosaicState, TileSnapshot } from '$lib/types';
  import '../app.css';

  let mosaic = $state<MosaicState | null>(null);
  let connection = $state<'connecting' | 'online' | 'retrying'>('connecting');
  let now = $state(new Date());

  const onlineCount = $derived(mosaic?.tiles.filter((tile) => tile.status === 'online').length ?? 0);
  const clock = $derived(new Intl.DateTimeFormat('pl-PL', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  }).format(now));

  const placeholders: TileSnapshot[] = Array.from({ length: 4 }, (_, index) => ({
    source_id: `waiting-${index}`,
    title: `Źródło ${index + 1}`,
    batch_id: '',
    frame_url: '',
    captured_at: new Date().toISOString(),
    position_seconds: 0,
    status: 'offline',
    error: null
  }));

  onMount(() => {
    const timer = window.setInterval(() => now = new Date(), 1000);
    void fetch('/api/mosaic')
      .then((response) => response.ok ? response.json() : null)
      .then((data: MosaicState | null) => { if (data) mosaic = data; })
      .catch(() => { connection = 'retrying'; });

    const events = new EventSource('/api/events');
    events.onopen = () => { connection = 'online'; };
    events.onerror = () => { connection = 'retrying'; };
    events.addEventListener('mosaic', (event) => {
      mosaic = JSON.parse((event as MessageEvent<string>).data) as MosaicState;
      connection = 'online';
    });

    return () => {
      window.clearInterval(timer);
      events.close();
    };
  });

</script>

<svelte:head><title>Mozaika TV</title></svelte:head>

<div class="app-shell">
  <header>
    <a class="brand" href="/" aria-label="Mozaika TV — strona główna">
      <span class="brand-mark"><i></i><i></i><i></i><i></i></span>
      <span><b>MOZAIKA</b><em>TV</em></span>
    </a>

    <div class="system-status">
      <span class="connection connection-{connection}"><i></i>{connection === 'online' ? 'SYSTEM ONLINE' : connection === 'retrying' ? 'PONAWIANIE' : 'ŁĄCZENIE'}</span>
      <span class="divider"></span>
      <span>{onlineCount}/4 ŹRÓDŁA</span>
    </div>

    <div class="clock">
      <span>CZAS LOKALNY</span>
      <strong>{clock}</strong>
    </div>
  </header>

  <main>
    <div class="section-label">
      <div>
        <span>PODGLĄD ZBIORCZY</span>
        <small>ODŚWIEŻANIE {mosaic?.next_refresh_seconds?.toFixed(1) ?? '—'} S</small>
      </div>
      <p>PARTIA <b>#{mosaic?.version?.toString().padStart(4, '0') ?? '0000'}</b></p>
    </div>

    <section class="mosaic" aria-label="Mozaika źródeł wideo">
      {#each mosaic?.tiles ?? placeholders as tile, index (tile.source_id)}
        <Tile {tile} {index} {now} />
      {/each}
    </section>
  </main>

  <footer>
    <span><i></i> AUTOMATYCZNA SYNCHRONIZACJA KLATEK</span>
    <span>RTV MCB UKSW</span>
  </footer>
</div>
