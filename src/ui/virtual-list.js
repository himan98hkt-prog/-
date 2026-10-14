// 가상 스크롤 — 원생 1,000명 이상에서도 DOM 노드를 화면에 보이는 만큼만 유지한다.
// 고정 행 높이 전제(측정 비용 0). 행 높이는 CSS 와 반드시 일치시킬 것.

export class VirtualList {
  /**
   * @param {HTMLElement} viewport overflow:auto 인 컨테이너
   * @param {object} opts { rowHeight, renderRow(item, index) => HTMLElement, overscan }
   */
  constructor(viewport, opts) {
    this.viewport = viewport
    this.rowHeight = opts.rowHeight || 64
    this.renderRow = opts.renderRow
    this.overscan = opts.overscan ?? 6
    this.items = []
    this.spacer = document.createElement('div')
    this.spacer.className = 'vl-spacer'
    this.canvas = document.createElement('div')
    this.canvas.className = 'vl-canvas'
    this.spacer.append(this.canvas)
    viewport.append(this.spacer)
    this._onScroll = () => this.draw()
    viewport.addEventListener('scroll', this._onScroll, { passive: true })
    this._ro = new ResizeObserver(() => this.draw())
    this._ro.observe(viewport)
  }

  setItems(items) {
    this.items = items || []
    this.spacer.style.height = `${this.items.length * this.rowHeight}px`
    this.viewport.scrollTop = Math.min(this.viewport.scrollTop, Math.max(0, this.items.length * this.rowHeight - this.viewport.clientHeight))
    this.draw()
  }

  draw() {
    const { scrollTop, clientHeight } = this.viewport
    const first = Math.max(0, Math.floor(scrollTop / this.rowHeight) - this.overscan)
    const visible = Math.ceil(clientHeight / this.rowHeight) + this.overscan * 2
    const last = Math.min(this.items.length, first + visible)
    const frag = document.createDocumentFragment()
    for (let i = first; i < last; i++) {
      const row = this.renderRow(this.items[i], i)
      row.style.position = 'absolute'
      row.style.top = `${i * this.rowHeight}px`
      row.style.left = '0'
      row.style.right = '0'
      row.style.height = `${this.rowHeight}px`
      frag.append(row)
    }
    this.canvas.replaceChildren(frag)
  }

  destroy() {
    this.viewport.removeEventListener('scroll', this._onScroll)
    this._ro.disconnect()
    this.spacer.remove()
  }
}
