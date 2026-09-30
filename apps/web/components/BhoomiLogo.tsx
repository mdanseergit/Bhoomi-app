import Image from "next/image";

interface BhoomiLogoProps {
  /** Width in pixels – height is calculated automatically */
  size?: number;
  /** Show the text "BHOOMI" beneath the logo */
  showText?: boolean;
  /** Additional CSS class */
  className?: string;
}

export function BhoomiLogo({ size = 48, showText = false, className = "" }: BhoomiLogoProps) {
  return (
    <div className={`flex flex-col items-center gap-1.5 ${className}`}>
      <Image
        src="/logo.jpeg"
        alt="BHOOMI — Agriculture Intelligence Platform"
        width={size}
        height={size}
        className="rounded-xl object-contain"
        priority
        style={{ width: size, height: size }}
      />
      {showText && (
        <div className="text-center">
          <p className="text-lg font-bold tracking-tight text-text-primary">BHOOMI</p>
          <p className="text-[11px] text-text-muted">Agriculture Intelligence</p>
        </div>
      )}
    </div>
  );
}
