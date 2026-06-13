import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatPercentage(value: number, decimals: number = 1): string {
  return `${value.toFixed(decimals)}%`
}

export function formatRounded(value: number, decimals: number = 2): string {
  return value.toFixed(decimals)
}

export function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t
}
