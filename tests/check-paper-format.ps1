$main = Get-Content -Raw -Encoding UTF8 'main.tex'
$references = Get-Content -Raw -Encoding UTF8 'sections/references.tex'
$bib = Get-Content -Raw -Encoding UTF8 'references.bib'

$checks = @(
  @{ Name = 'registration number'; Pass = $main.Contains('\newcommand{\registrationNumber}{009842}') },
  @{ Name = 'cover registration label macro'; Pass = $main.Contains('\newcommand{\registrationLabel}') },
  @{ Name = 'old underlined cover fields removed'; Pass = -not $main.Contains('\underline{\makebox[8cm]') },
  @{ Name = 'references no toc entry'; Pass = -not $references.Contains('\addcontentsline{toc}') },
  @{ Name = 'BibTeX references entrypoint'; Pass = $references.Contains('\bibliography{references}') },
  @{ Name = 'official policy reference'; Pass = $bib.Contains('ndrc2025green-direct') },
  @{ Name = 'Times-like math font'; Pass = $main.Contains('\usepackage{newtxmath}') },
  @{ Name = 'display math spacing'; Pass = $main.Contains('\setlength{\abovedisplayskip}') },
  @{ Name = 'single spacing'; Pass = $main.Contains('\setstretch{1.0}') },
  @{ Name = 'section visual hierarchy'; Pass = $main.Contains('\newcommand{\sectiontitlefont}{\heiti\fontsize{18bp}{25bp}\selectfont}') },
  @{ Name = 'caption Kai font'; Pass = $main.Contains('\DeclareCaptionFont{captionkai}{\kaishu\zihao{-4}\setstretch{1.0}}') },
  @{ Name = 'table font helper'; Pass = $main.Contains('\newcommand{\tablefont}{\songti\zihao{-4}}') },
  @{ Name = 'old line spread removed'; Pass = -not $main.Contains('\linespread{1.25}') }
)

$failed = $checks | Where-Object { -not $_.Pass }
if ($failed) {
  $failed | ForEach-Object { Write-Error "Missing paper format rule: $($_.Name)" }
  exit 1
}

Write-Output 'Paper format source checks passed.'
