local util = loadScript("/SCRIPTS/TOOLS/lib/util.lua")()

local function run(event)
  lcd.clear()
  lcd.drawText(1, 1, util.greeting("EdgeTX"), 0)
  return 0
end

return { run = run }
