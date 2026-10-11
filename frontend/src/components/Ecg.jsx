export default function Ecg() {
  // the monitor trace: one beat, repeated; drawn by animating the dash offset, with a fading echo behind the bright head
  const beat = "l40 0 l6 -6 l6 6 l8 0 l4 -34 l6 70 l5 -36 l6 0 l8 0 l10 -10 l10 10 l35 0";
  const d = "M -200 100 " + Array.from({ length: 14 }, () => beat).join(" ");
  return (<svg className="ecg" viewBox="0 0 1600 200" preserveAspectRatio="none" aria-hidden="true">
    <path className="ecg-grid" d={Array.from({ length: 9 }, (_, i) => `M0 ${i * 25} H1600`).join(" ") + Array.from({ length: 33 }, (_, i) => `M${i * 50} 0 V200`).join(" ")} />
    <path className="ecg-echo" d={d} />
    <path className="ecg-line" d={d} />
  </svg>);
}
