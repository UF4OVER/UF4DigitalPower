from app.Config import cfg
from qfluentwidgets import qconfig, Theme, isDarkTheme

print('cfg.themeMode before:', cfg.get(cfg.themeMode))
print('qconfig.theme before:', qconfig.theme)
print('isDarkTheme() before:', isDarkTheme())

# Switch to DARK
cfg.set(cfg.themeMode, Theme.DARK, save=False)

print('cfg.themeMode after set to DARK:', cfg.get(cfg.themeMode))
print('qconfig.theme after:', qconfig.theme)
print('isDarkTheme() after:', isDarkTheme())

# Switch back to LIGHT
cfg.set(cfg.themeMode, Theme.LIGHT, save=False)
print('cfg.themeMode after set to LIGHT:', cfg.get(cfg.themeMode))
print('qconfig.theme after:', qconfig.theme)
print('isDarkTheme() after light:', isDarkTheme())
