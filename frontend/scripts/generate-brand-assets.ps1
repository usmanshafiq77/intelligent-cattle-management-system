param()

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$assetRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\assets"))

function New-RoundedRectanglePath([float]$x, [float]$y, [float]$width, [float]$height, [float]$radius) {
  $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $diameter = $radius * 2
  $path.AddArc($x, $y, $diameter, $diameter, 180, 90)
  $path.AddArc($x + $width - $diameter, $y, $diameter, $diameter, 270, 90)
  $path.AddArc($x + $width - $diameter, $y + $height - $diameter, $diameter, $diameter, 0, 90)
  $path.AddArc($x, $y + $height - $diameter, $diameter, $diameter, 90, 90)
  $path.CloseFigure()
  return $path
}

function Draw-Mark($graphics, [float]$x, [float]$y, [float]$size, [bool]$withTile, [System.Drawing.Color]$lineColor) {
  $scale = $size / 512.0
  if ($withTile) {
    $tilePath = New-RoundedRectanglePath ($x + 32 * $scale) ($y + 32 * $scale) (448 * $scale) (448 * $scale) (128 * $scale)
    $gradient = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
      [System.Drawing.PointF]::new($x, $y),
      [System.Drawing.PointF]::new($x + $size, $y + $size),
      [System.Drawing.ColorTranslator]::FromHtml("#075C4B"),
      [System.Drawing.ColorTranslator]::FromHtml("#1AB69D")
    )
    $graphics.FillPath($gradient, $tilePath)
    $gradient.Dispose()
    $tilePath.Dispose()
  }

  $pen = [System.Drawing.Pen]::new($lineColor, 22 * $scale)
  $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $graphics.DrawBezier($pen, $x + 178 * $scale, $y + 191 * $scale, $x + 144 * $scale, $y + 166 * $scale, $x + 117 * $scale, $y + 173 * $scale, $x + 100 * $scale, $y + 199 * $scale)
  $graphics.DrawBezier($pen, $x + 334 * $scale, $y + 191 * $scale, $x + 368 * $scale, $y + 166 * $scale, $x + 395 * $scale, $y + 173 * $scale, $x + 412 * $scale, $y + 199 * $scale)

  $facePath = New-RoundedRectanglePath ($x + 154 * $scale) ($y + 169 * $scale) (204 * $scale) (226 * $scale) (82 * $scale)
  $graphics.DrawPath($pen, $facePath)
  $facePath.Dispose()

  $brush = [System.Drawing.SolidBrush]::new($lineColor)
  $graphics.FillEllipse($brush, $x + 206 * $scale, $y + 240 * $scale, 20 * $scale, 20 * $scale)
  $graphics.FillEllipse($brush, $x + 286 * $scale, $y + 240 * $scale, 20 * $scale, 20 * $scale)
  $muzzlePen = [System.Drawing.Pen]::new($lineColor, 16 * $scale)
  $muzzlePath = New-RoundedRectanglePath ($x + 202 * $scale) ($y + 303 * $scale) (108 * $scale) (54 * $scale) (27 * $scale)
  $graphics.DrawPath($muzzlePen, $muzzlePath)

  $leafBrush = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml("#D5A64B"))
  $leaf = [System.Drawing.Drawing2D.GraphicsPath]::new()
  $leaf.AddBezier($x + 356 * $scale, $y + 103 * $scale, $x + 400 * $scale, $y + 110 * $scale, $x + 424 * $scale, $y + 141 * $scale, $x + 420 * $scale, $y + 185 * $scale)
  $leaf.AddBezier($x + 420 * $scale, $y + 185 * $scale, $x + 377 * $scale, $y + 178 * $scale, $x + 352 * $scale, $y + 147 * $scale, $x + 356 * $scale, $y + 103 * $scale)
  $leaf.CloseFigure()
  $graphics.FillPath($leafBrush, $leaf)

  $leaf.Dispose()
  $leafBrush.Dispose()
  $muzzlePath.Dispose()
  $muzzlePen.Dispose()
  $brush.Dispose()
  $pen.Dispose()
}

function Save-Canvas([string]$name, [int]$size, [System.Drawing.Color]$background, [scriptblock]$draw) {
  $bitmap = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
  $graphics.Clear($background)
  & $draw $graphics $size
  $path = Join-Path $assetRoot $name
  $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose()
  $bitmap.Dispose()
}

$transparent = [System.Drawing.Color]::Transparent
$cream = [System.Drawing.ColorTranslator]::FromHtml("#F8FFF9")
$emerald = [System.Drawing.ColorTranslator]::FromHtml("#075C4B")

Save-Canvas "icon.png" 1024 $emerald { param($g, $s) Draw-Mark $g 0 0 $s $true $cream }
Save-Canvas "splash-icon.png" 1024 $transparent { param($g, $s) Draw-Mark $g 72 72 880 $true $cream }
Save-Canvas "android-icon-foreground.png" 1024 $transparent { param($g, $s) Draw-Mark $g 205 205 614 $false $cream }
Save-Canvas "android-icon-background.png" 1024 $emerald { param($g, $s) }
Save-Canvas "android-icon-monochrome.png" 1024 $transparent { param($g, $s) Draw-Mark $g 205 205 614 $false ([System.Drawing.Color]::White) }
Save-Canvas "favicon.png" 64 $emerald { param($g, $s) Draw-Mark $g 0 0 $s $true $cream }

Write-Host "Generated ICMS brand assets in $assetRoot"
