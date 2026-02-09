$out_dir = 'build';
$aux_dir = 'build';
$pdf_mode = 1;
$pdflatex = 'xelatex %O %S';
$ENV{'BIBINPUTS'} = ".:..:";
$bibtex_use = 2;
$ENV{'TEXINPUTS'} = ".:build:..:";