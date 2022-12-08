/*
Add this to your configuration.yaml
frontend:
  extra_module_url:
    - /local/system/theme-override.js

And put the following into <config-dir>/www/system/theme-override.js
*/
console.info('%c  THEME-OVERRIDE  \n%c  Version 1.0.3   ', 'color: white; font-weight: bold; background: navy', 'color: white; font-weight: bold; background: dimgray');

document.documentElement.style.setProperty('--ha-card-border-radius', '3px');
document.documentElement.style.setProperty('--ha-card-border-color', 'transparent');
document.documentElement.style.setProperty('--bar-card-border-radius', '1px');

document.documentElement.style.setProperty('--rgb-state-binary-sensor-color', 'var(--rgb-yellow-color)');