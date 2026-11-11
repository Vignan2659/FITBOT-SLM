import { useCallback, useEffect, useRef, useState } from "react";

// Live heart rate over Bluetooth (the standard Heart Rate service that chest straps and many bands broadcast).
// Works in Chrome and Edge; Safari and Firefox have no Web Bluetooth.
export const bluetoothSupported = typeof navigator !== "undefined" && Boolean(navigator.bluetooth);

// Heart Rate Measurement characteristic: bit 0 of the flags byte says whether the value is 8 or 16 bit.
export function parseHeartRate(view) {
  const wide = view.getUint8(0) & 1;
  return wide ? view.getUint16(1, true) : view.getUint8(1);
}

export function sessionStats(samples) {
  if (!samples.length) return { avg: null, max: null, min: null };
  const values = samples.map((s) => s.bpm);
  return { avg: Math.round(values.reduce((a, b) => a + b, 0) / values.length), max: Math.max(...values), min: Math.min(...values) };
}

export default function useHeartRate() {
  const [status, setStatus] = useState("idle");        // idle | connecting | live | error
  const [device, setDevice] = useState("");
  const [bpm, setBpm] = useState(null);
  const [samples, setSamples] = useState([]);           // [{ t: ms, bpm }]
  const [startedAt, setStartedAt] = useState(null);
  const [error, setError] = useState("");
  const ref = useRef({ device: null, characteristic: null });

  const onValue = useCallback((event) => {
    const value = parseHeartRate(event.target.value);
    if (value < 25 || value > 240) return;
    setBpm(value);
    setSamples((s) => [...s.slice(-3599), { t: Date.now(), bpm: value }]);
  }, []);

  const disconnect = useCallback(() => {
    const { device: d, characteristic: c } = ref.current;
    try { c?.removeEventListener("characteristicvaluechanged", onValue); } catch { /* already gone */ }
    try { if (d?.gatt?.connected) d.gatt.disconnect(); } catch { /* already gone */ }
    ref.current = { device: null, characteristic: null };
    setStatus("idle");
    setBpm(null);
  }, [onValue]);

  const connect = useCallback(async () => {
    setError("");
    if (!bluetoothSupported) {
      setError("This browser has no Bluetooth support. Open FitBot in Chrome or Edge to use live heart rate.");
      setStatus("error");
      return;
    }
    try {
      setStatus("connecting");
      const d = await navigator.bluetooth.requestDevice({ filters: [{ services: ["heart_rate"] }] });
      d.addEventListener("gattserverdisconnected", () => { setStatus("idle"); setBpm(null); });
      const server = await d.gatt.connect();
      const service = await server.getPrimaryService("heart_rate");
      const c = await service.getCharacteristic("heart_rate_measurement");
      c.addEventListener("characteristicvaluechanged", onValue);
      await c.startNotifications();
      ref.current = { device: d, characteristic: c };
      setDevice(d.name || "Heart rate sensor");
      setSamples([]);
      setStartedAt(new Date());
      setStatus("live");
    } catch (e) {
      // closing the device picker is not an error worth showing
      setError(e?.name === "NotFoundError" ? "" : "Could not connect. Turn on heart rate broadcast on the band, keep it close and try again.");
      setStatus(e?.name === "NotFoundError" ? "idle" : "error");
    }
  }, [onValue]);

  useEffect(() => disconnect, [disconnect]);

  const reset = useCallback(() => { setSamples([]); setStartedAt(null); }, []);
  return { status, device, bpm, samples, startedAt, error, connect, disconnect, reset };
}
