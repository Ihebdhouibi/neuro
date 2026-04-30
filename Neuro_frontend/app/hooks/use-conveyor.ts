type ConveyorKey = keyof Window['conveyor']

/**
 * Use the conveyor for inter-process communication
 *
 * @param key - The key of the conveyor object to use
 * @returns The conveyor object or the keyed object
 */
export const useConveyor = <T extends ConveyorKey | undefined = undefined>(
  key?: T
): T extends ConveyorKey ? Window['conveyor'][T] : Window['conveyor'] => {
  // Guard: conveyor is injected by the Electron preload script. Without it
  // (e.g. in a non-Electron context, or before preload finishes), return
  // undefined so callers can safely optional-chain instead of crashing.
  if (typeof window === 'undefined' || !(window as any).conveyor) {
    return undefined as any
  }

  const conveyor = window.conveyor

  if (key) {
    return conveyor[key] as any
  }

  return conveyor as any
}
