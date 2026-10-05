import {
  ArrowRightIcon as ArrowRight,
  CaretRightIcon as CaretRight,
  CheckIcon as Check,
  FileTextIcon as FileText,
  FolderIcon as Folder,
  InfoIcon as Info,
  MagnifyingGlassIcon as MagnifyingGlass,
  MoonIcon as Moon,
  SlidersHorizontalIcon as SlidersHorizontal,
  SunIcon as Sun,
  WarningIcon as Warning,
  XIcon as X,
  type Icon,
  type IconProps as PhosphorProps,
} from "@phosphor-icons/react";
import type { SVGProps } from "react";

// Interface glyphs come from Phosphor at one weight, so every stroke matches.
// Only the brand mark below is drawn by hand: it is the logo, not an icon.
type IconProps = Omit<PhosphorProps, "weight"> & { size?: number };

function glyph(Glyph: Icon, weight: PhosphorProps["weight"] = "regular") {
  return function AppIcon({ size = 18, ...props }: IconProps) {
    return <Glyph aria-hidden="true" size={size} weight={weight} {...props} />;
  };
}

export const ArrowRightIcon = glyph(ArrowRight);
export const ChevronIcon = glyph(CaretRight);
export const CloseIcon = glyph(X);
export const DocumentIcon = glyph(FileText);
export const FolderIcon = glyph(Folder);
export const InfoIcon = glyph(Info);
export const SearchIcon = glyph(MagnifyingGlass);
export const SlidersIcon = glyph(SlidersHorizontal);
export const WarningIcon = glyph(Warning);
export const CheckIcon = glyph(Check, "bold");
export const MoonIcon = glyph(Moon);
export const SunIcon = glyph(Sun);

export const BrandMark = ({ size = 18, ...props }: SVGProps<SVGSVGElement> & { size?: number }) => (
  <svg aria-hidden="true" fill="none" height={size} viewBox="0 0 24 24" width={size} {...props}>
    <path d="M6 3.5h9l3.5 3.5v13.5H6z" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.6" />
    <path d="M9 11.5h6.5M9 15h6.5M9 18.5h3.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" />
    <path d="M3.5 7v13.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.6" />
  </svg>
);
