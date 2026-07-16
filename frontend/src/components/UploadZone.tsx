import { useRef, useState, type DragEvent } from 'react'

const ACCEPT = '.jpg,.jpeg,.png,.pdf,.docx'

interface Props {
  multiple?: boolean
  disabled?: boolean
  onFiles: (files: File[]) => void
}

export function UploadZone({ multiple = false, disabled = false, onFiles }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const pick = (list: FileList | null) => {
    if (!list || list.length === 0) return
    onFiles(multiple ? Array.from(list) : [list[0]])
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    if (!disabled) pick(e.dataTransfer.files)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={
        'card flex cursor-pointer flex-col items-center justify-center gap-2 border-dashed px-6 py-12 text-center transition ' +
        (over ? 'border-accent ring-2 ring-accent/30 ' : '') +
        (disabled ? 'pointer-events-none opacity-50' : 'hover:border-accent')
      }
    >
      <div className="text-3xl" aria-hidden>
        ⬆️
      </div>
      <div className="font-semibold">
        {multiple ? 'גרור טפסים לכאן, או לחץ לבחירה' : 'גרור טופס לכאן, או לחץ לבחירה'}
      </div>
      <div className="field-label">JPG · PNG · PDF · DOCX</div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple={multiple}
        hidden
        onChange={(e) => pick(e.target.files)}
      />
    </div>
  )
}
