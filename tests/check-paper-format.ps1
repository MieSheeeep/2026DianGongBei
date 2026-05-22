$main = Get-Content -Raw -Encoding UTF8 'main.tex'
$references = Get-Content -Raw -Encoding UTF8 'sections/references.tex'

$checks = @(
  @{ Name = 'registration number'; Pass = $main.Contains('\newcommand{\registrationNumber}{009842}') },
  @{ Name = 'cover registration label macro'; Pass = $main.Contains('\newcommand{\registrationLabel}') },
  @{ Name = 'old underlined cover fields removed'; Pass = -not $main.Contains('\underline{\makebox[8cm]') },
  @{ Name = 'references no toc entry'; Pass = -not $references.Contains('\addcontentsline{toc}') },
  @{ Name = 'citation marker guidance'; Pass = $references.Contains('[1][3]') },
  @{ Name = 'Times-like math font'; Pass = $main.Contains('\usepackage{newtxmath}') },
  @{ Name = 'display math spacing'; Pass = $main.Contains('\setlength{\abovedisplayskip}') }
)

$failed = $checks | Where-Object { -not $_.Pass }
if ($failed) {
  $failed | ForEach-Object { Write-Error "Missing paper format rule: $($_.Name)" }
  exit 1
}

Write-Output 'Paper format source checks passed.'
