/**
 * Рівень гучності для VoiceButton (DESIGN.md §4.1): пише `--level` (0…1) у CSS-змінну елемента без ре-рендерів.
 * Повертає функцію зупинки. Сам стрім не зупиняє: ним володіє той, хто його відкрив.
 */
export function attachLevelMeter(stream: MediaStream, getEl: () => HTMLElement | null): () => void {
  if (typeof AudioContext === 'undefined') return () => {}
  const ctx = new AudioContext()
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 512
  ctx.createMediaStreamSource(stream).connect(analyser)
  const data = new Uint8Array(analyser.fftSize)
  let raf = 0
  let active = true

  const tick = () => {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (const v of data) sum += ((v - 128) / 128) ** 2
    const rms = Math.sqrt(sum / data.length)
    getEl()?.style.setProperty('--level', Math.min(1, rms * 4).toFixed(2))
    if (active) raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)

  return () => {
    active = false
    cancelAnimationFrame(raf)
    void ctx.close()
    getEl()?.style.setProperty('--level', '0')
  }
}
