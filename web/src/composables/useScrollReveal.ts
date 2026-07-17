import { onMounted, onUnmounted } from 'vue'

export function useScrollReveal(rootSelector: string): void {
  let observer: IntersectionObserver | undefined

  onMounted(() => {
    const root = document.querySelector<HTMLElement>(rootSelector)
    if (!root) return

    const targets = root.querySelectorAll<HTMLElement>('[data-reveal]')
    root.classList.add('reveal-ready')

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      targets.forEach((target) => target.classList.add('is-visible'))
      return
    }

    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('is-visible')
        observer?.unobserve(entry.target)
      })
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 })

    targets.forEach((target) => observer?.observe(target))
  })

  onUnmounted(() => observer?.disconnect())
}
