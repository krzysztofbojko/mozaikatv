<script lang="ts">
  import type { TileSnapshot } from './types';

  interface Props {
    tile: TileSnapshot;
    index: number;
    now: Date;
  }

  let { tile, index, now }: Props = $props();
  let currentUrl = $state('');
  let previousUrl = $state('');

  const ageSeconds = $derived(
    Math.max(0, Math.round((now.getTime() - new Date(tile.captured_at).getTime()) / 1000))
  );
  const statusText = $derived(
    tile.status === 'online'
      ? 'AKTYWNY'
      : tile.status === 'delayed'
        ? 'OPÓŹNIONY'
        : tile.status === 'disabled'
          ? 'WYŁĄCZONY'
          : 'OFFLINE'
  );

  $effect(() => {
    const nextUrl = tile.frame_url;
    if (!nextUrl) {
      previousUrl = '';
      currentUrl = '';
      return;
    }
    if (nextUrl === currentUrl || typeof Image === 'undefined') return;

    let cancelled = false;
    const image = new Image();
    image.src = nextUrl;
    const show = () => {
      if (cancelled) return;
      previousUrl = currentUrl;
      currentUrl = nextUrl;
      window.setTimeout(() => {
        if (currentUrl === nextUrl) previousUrl = '';
      }, 280);
    };
    image.decode().then(show).catch(() => {
      image.onload = show;
    });
    return () => {
      cancelled = true;
    };
  });
</script>

<article class="tile status-{tile.status}">
  <div class="viewport">
    {#if tile.status !== 'disabled'}
    {#if previousUrl}
      <img class="frame previous" src={previousUrl} alt="" aria-hidden="true" />
    {/if}
    {#if currentUrl}
      <img class="frame current" src={currentUrl} alt={`Klatka źródła ${tile.title}`} />
    {:else}
      <div class="placeholder">
        <span class="loader"></span>
        <span>OCZEKIWANIE NA KLATKĘ</span>
      </div>
    {/if}
    <div class="scanline"></div>
    <div class="shade"></div>
    <span class="corner corner-tl" aria-hidden="true"></span>
    <span class="corner corner-tr" aria-hidden="true"></span>
    <span class="corner corner-bl" aria-hidden="true"></span>
    <span class="corner corner-br" aria-hidden="true"></span>

    <div class="topline">
      <span class="source-number">0{index + 1}</span>
      <span class="status"><i></i>{statusText}</span>
    </div>

    <div class="caption">
      <div>
        <p>ŹRÓDŁO {index + 1}</p>
        <h2>{tile.title}</h2>
      </div>
      <div class="meta">
        <span>{ageSeconds < 2 ? 'TERAZ' : `${ageSeconds} S TEMU`}</span>
        <span>{Math.floor(tile.position_seconds / 60).toString().padStart(2, '0')}:{Math.floor(tile.position_seconds % 60).toString().padStart(2, '0')}</span>
      </div>
    </div>
    {/if}

  </div>
</article>

<style>
  .tile {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 18px;
    background: #030405;
    box-shadow:
      0 18px 50px rgb(0 0 0 / 28%),
      inset 0 0 0 1px rgb(255 255 255 / 2%);
  }

  .tile.status-delayed { border-color: rgb(255 180 42 / 52%); }
  .tile.status-offline { border-color: rgb(255 81 93 / 55%); }
  .tile.status-disabled { border-color: rgb(255 255 255 / 5%); box-shadow: none; }

  .viewport { position: relative; width: 100%; height: 100%; overflow: hidden; }
  .frame { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .frame.previous { z-index: 1; }
  .frame.current { z-index: 2; animation: reveal 260ms ease-out both; }

  @keyframes reveal {
    from { opacity: 0; transform: scale(1.008); }
    to { opacity: 1; transform: scale(1); }
  }

  .placeholder {
    position: absolute;
    inset: 0;
    display: grid;
    place-content: center;
    justify-items: center;
    gap: 14px;
    color: var(--muted);
    font-size: 10px;
    letter-spacing: .18em;
  }

  .loader {
    width: 28px;
    height: 28px;
    border: 2px solid rgb(255 255 255 / 10%);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .scanline {
    position: absolute;
    z-index: 3;
    inset: 0;
    pointer-events: none;
    opacity: .06;
    background: repeating-linear-gradient(180deg, transparent 0 3px, #fff 4px);
    mix-blend-mode: overlay;
  }
  .shade {
    position: absolute;
    z-index: 4;
    inset: 0;
    pointer-events: none;
    background: linear-gradient(180deg, rgb(0 0 0 / 35%) 0%, transparent 35%, transparent 55%, rgb(0 0 0 / 86%) 100%);
  }

  .corner {
    position: absolute;
    z-index: 6;
    width: 22px;
    height: 22px;
    pointer-events: none;
    opacity: .56;
  }
  .corner-tl { top: 8px; left: 8px; border-top: 1px solid var(--accent); border-left: 1px solid var(--accent); border-radius: 5px 0 0; }
  .corner-tr { top: 8px; right: 8px; border-top: 1px solid var(--accent); border-right: 1px solid var(--accent); border-radius: 0 5px 0 0; }
  .corner-bl { bottom: 8px; left: 8px; border-bottom: 1px solid var(--accent); border-left: 1px solid var(--accent); border-radius: 0 0 0 5px; }
  .corner-br { right: 8px; bottom: 8px; border-right: 1px solid var(--accent); border-bottom: 1px solid var(--accent); border-radius: 0 0 5px; }

  .topline {
    position: absolute;
    z-index: 5;
    top: 14px;
    left: 14px;
    right: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .source-number {
    display: grid;
    place-items: center;
    width: 31px;
    height: 27px;
    border: 1px solid rgb(255 255 255 / 25%);
    border-radius: 7px;
    background: rgb(0 0 0 / 55%);
    backdrop-filter: blur(8px);
    color: white;
    font: 650 11px/1 var(--mono);
  }
  .status {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 9px;
    border-radius: 999px;
    background: rgb(0 0 0 / 55%);
    backdrop-filter: blur(8px);
    color: white;
    font: 650 9px/1 var(--mono);
    letter-spacing: .12em;
  }
  .status i { width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); }
  .status-delayed .status i { background: var(--amber); box-shadow: 0 0 10px var(--amber); }
  .status-offline .status i { background: var(--red); box-shadow: 0 0 10px var(--red); }

  .caption {
    position: absolute;
    z-index: 5;
    left: 17px;
    right: 17px;
    bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 16px;
  }
  .caption p { margin: 0 0 5px; color: var(--accent); font: 650 9px/1 var(--mono); letter-spacing: .14em; }
  .caption h2 { margin: 0; color: #fff; font-size: clamp(16px, 1.45vw, 24px); font-weight: 590; letter-spacing: -.025em; text-transform: capitalize; }
  .meta { display: grid; justify-items: end; gap: 5px; flex: 0 0 auto; color: rgb(255 255 255 / 68%); font: 550 9px/1 var(--mono); letter-spacing: .08em; }

  @media (max-width: 720px) {
    .tile { min-height: 250px; aspect-ratio: 16 / 9; }
  }

  @media (prefers-reduced-motion: reduce) {
    .frame.current, .loader { animation: none; }
  }
</style>
