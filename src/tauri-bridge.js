// Thin wrapper around window.__TAURI__ for dual-mode (Tauri / browser) support.
// With withGlobalTauri: true in tauri.conf.json, the Tauri runtime injects
// window.__TAURI__ with .core.invoke and .event.listen.

// Delayed access: read window.__TAURI__ at call time, not module load time.
// Tauri 2.0 injects the global before page scripts run, but being defensive
// avoids false negatives if module evaluation races the injection.

function checkTauri() {
  return typeof window !== 'undefined' && Boolean(window.__TAURI__) &&
         Boolean(window.__TAURI__?.core?.invoke);
}

// isTauri is checked lazily — re-evaluated at each call to avoid module-load race.
export const isTauri = checkTauri();

export async function invoke(command, args) {
  const t = window.__TAURI__;
  if (!t || !t.core || !t.core.invoke) {
    throw new Error(`invoke not available: window.__TAURI__=${typeof t}`);
  }
  return t.core.invoke(command, args);
}

export async function listen(event, handler) {
  const t = window.__TAURI__;
  if (!t || !t.event || !t.event.listen) {
    console.error('[tauri-bridge] event.listen not available. window.__TAURI__ =', t);
    throw new Error(`listen not available for event: ${event}`);
  }
  return t.event.listen(event, handler);
}
