# 通过 Windows UIAutomation 关闭指定标题的浏览器标签页
# 用于扩展页（chrome-extension://）等 Playwright 无法收购的标签
#
# 用法：
#   powershell -File close_tab_uia.ps1 -TitleLike "*复习讲义*"
#   powershell -File close_tab_uia.ps1 -TitleLike "*复习讲义*" -BrowserName "Tabbit"
#
# 原理：Chrome 系浏览器的 TabItem 下有一个名为「关闭」的 Button，
#       用 InvokePattern 点它等价于点标签上的 ×（不需要前台激活窗口）

param(
    [Parameter(Mandatory = $true)][string]$TitleLike,
    [string]$BrowserName = "Tabbit"
)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$winCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ClassNameProperty, "Chrome_WidgetWin_1")
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $winCond) |
    Where-Object { $_.Current.Name -like "*$BrowserName*" }

if (-not $windows) { Write-Output "未找到 $BrowserName 窗口"; exit 1 }

$tabCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::TabItem)

$closed = 0
foreach ($w in $windows) {
    $tabs = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $tabCond)
    foreach ($t in $tabs) {
        if ($t.Current.Name -notlike $TitleLike) { continue }
        $kids = $t.FindAll([System.Windows.Automation.TreeScope]::Children,
                           [System.Windows.Automation.Condition]::TrueCondition)
        $btn = $kids | Where-Object { $_.Current.Name -eq "关闭" } | Select-Object -First 1
        if (-not $btn) { continue }
        try {
            $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
            $closed++
            Start-Sleep -Milliseconds 600
            Write-Output ("已关闭: " + $t.Current.Name.Substring(0, [Math]::Min(60, $t.Current.Name.Length)))
        } catch {
            Write-Output ("关闭失败: " + $_.Exception.Message)
        }
    }
}

if ($closed -eq 0) { Write-Output "没有匹配的标签页" } else { Write-Output "共关闭 $closed 个标签" }
