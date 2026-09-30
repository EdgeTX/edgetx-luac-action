local M = {}

function M.greeting(name)
  return "Hello " .. name .. " " .. (7 // 2) .. " " .. (1.5 * 2)
end

return M
