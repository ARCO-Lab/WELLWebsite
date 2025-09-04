// This file provides utility functions for class name merging and Tailwind CSS integration.
// The 'cn' function combines class names using clsx and tailwind-merge.

import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  // Merge class names conditionally and resolve Tailwind conflicts
  return twMerge(clsx(inputs))
}
