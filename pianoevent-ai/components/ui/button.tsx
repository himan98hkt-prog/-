import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * 단추.
 *
 * 예전에는 `transition-colors` 하나뿐이었다. 얹었을 때만 색이 조금 바뀌고
 * **누를 때는 아무 일도 일어나지 않았다.** 마우스를 쓰지 않는 분, 눈이 편치 않은 분께는
 * 눌렀는지 아닌지 알 길이 없는 화면이었다.
 *
 * 지금은 누르면 셋이 한꺼번에 일어난다(`.press`) —
 * 1px 내려앉고, 아주 살짝 줄고, 둘레에 강조색 테가 번진다.
 * 채워진 단추에는 윗면 1px 밝은 선을 넣어 도톰해 보이게 했다(`.press-filled`).
 *
 * 얹었을 때의 변화는 `@media (hover: hover)` 안에만 둔다.
 * 손가락으로 만지는 화면에서는 "얹은 상태"가 눌린 뒤에도 남아 붙어 버린다.
 *
 * 윗면 광택은 **CSS(`.press-filled`)에 둔다.** 여기에 `bg-gradient-to-b` 를 적었더니
 * `tailwind-merge` 가 그것을 배경색과 같은 갈래로 보고 `bg-primary` 를 지워 버렸다.
 * 「연주회 만들기」가 글씨도 배경도 없는 흰 상자가 됐다 — 화면을 찍어 보고서야 알았다.
 */
const buttonVariants = cva(
  'press inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'press-filled bg-primary text-primary-foreground hover:bg-primary/90 active:bg-primary',
        accent: 'press-filled bg-accent text-accent-foreground hover:bg-accent/90 active:bg-accent',
        outline: 'border border-input bg-card hover:bg-secondary hover:border-accent/50',
        ghost: 'hover:bg-secondary',
        destructive:
          'press-filled bg-destructive text-destructive-foreground hover:bg-destructive/90 active:bg-destructive',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 rounded px-3 text-xs',
        lg: 'h-12 px-6 text-base',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
)
Button.displayName = 'Button'

export { buttonVariants }
