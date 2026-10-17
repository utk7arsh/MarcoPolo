const stamp = () => new Date().toISOString().slice(11, 23);

export const log = {
  info: (...args: unknown[]) => console.log(stamp(), ...args),
  warn: (...args: unknown[]) => console.warn(stamp(), "WARN", ...args),
  error: (...args: unknown[]) => console.error(stamp(), "ERROR", ...args),
};
