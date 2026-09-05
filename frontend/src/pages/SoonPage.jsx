import { Card } from '@/components/ui/card'

export function SoonPage({ title, description }) {
  return (
    <Card className="mx-auto mt-16 max-w-xl px-8 py-12 text-center">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </Card>
  )
}
