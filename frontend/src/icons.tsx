import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function IconBase({ size = 18, children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      {...props}
    >
      {children}
    </svg>
  );
}

export const ArrowRightIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M5 12h14m-5-5 5 5-5 5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></IconBase>
);
export const ChevronIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m9 6 6 6-6 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></IconBase>
);
export const CloseIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" /></IconBase>
);
export const DocumentIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M7 3h7l4 4v14H7zM14 3v5h4M9.5 13h6M9.5 16h6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" /></IconBase>
);
export const FolderIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M3 7.5h7l2-2h9v14H3z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /></IconBase>
);
export const InfoIcon = (props: IconProps) => (
  <IconBase {...props}><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" /><path d="M12 11v6m0-9.5v.1" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></IconBase>
);
export const SearchIcon = (props: IconProps) => (
  <IconBase {...props}><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" strokeWidth="1.7" /><path d="m15.5 15.5 4 4" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" /></IconBase>
);
export const SlidersIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M4 7h10M18 7h2M4 17h2m4 0h10M9 4v6m0 4v6M17 4v6" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>
);
export const WarningIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m12 3 9 17H3z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /><path d="M12 9v4m0 3v.1" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" /></IconBase>
);
export const CheckIcon = (props: IconProps) => (
  <IconBase {...props}><path d="m5 12.5 4.5 4.5L19 7.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></IconBase>
);
export const MoonIcon = (props: IconProps) => (
  <IconBase {...props}><path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /></IconBase>
);
export const SunIcon = (props: IconProps) => (
  <IconBase {...props}><circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.6" /><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>
);
export const BrandMark = (props: IconProps) => (
  <IconBase {...props}><path d="M6 3.5h9l3.5 3.5v13.5H6z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" /><path d="M9 11.5h6.5M9 15h6.5M9 18.5h3.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /><path d="M3.5 7v13.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" /></IconBase>
);
