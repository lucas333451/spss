#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(optparse)
  library(readr)
  library(dplyr)
  library(stringr)
  library(lme4)
  library(lmerTest)
  library(emmeans)
  library(broom.mixed)
})

option_list <- list(
  make_option(c("--long-csv"), type="character", help="Path to results/long/long_format.csv"),
  make_option(c("--out-dir"), type="character", default="results/r_model", help="Output directory"),
  make_option(c("--df-method"), type="character", default="Satterthwaite", help="Satterthwaite|Kenward-Roger"),
  make_option(c("--p-adjust"), type="character", default="Holm", help="Holm|bonferroni|fdr|none")
)
opt <- parse_args(OptionParser(option_list=option_list))

# optparse may keep names with hyphens; support both forms
out_dir <- opt$`out-dir`
if (is.null(out_dir)) out_dir <- opt$out_dir
out_dir <- as.character(out_dir)[1]
if (is.na(out_dir) || out_dir == "") out_dir <- "results/r_model"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive=TRUE)

# df-method handling
# lmerTest uses Satterthwaite by default; Kenward-Roger requires pbkrtest.
df_method <- opt$`df-method`
if (tolower(df_method) %in% c("kenward-roger", "kenwardroger", "kr")) {
  if (!requireNamespace("pbkrtest", quietly = TRUE)) {
    stop("Kenward-Roger requested but pbkrtest is not installed. Install pbkrtest or use Satterthwaite.")
  }
}

# read data
long_csv <- opt$`long-csv`
if (is.null(long_csv)) stop("--long-csv is required")
long_csv <- as.character(long_csv)[1]

x <- read_csv(long_csv, show_col_types = FALSE)

# basic checks
req <- c("SubjectID","S1","S2","S3","S4","WWR","Complexity","ExperienceGroup","SportFreqGroup","Repetition","Position")
miss <- setdiff(req, names(x))
if (length(miss) > 0) stop(paste("Missing columns:", paste(miss, collapse=", ")))

# build Afford4
x <- x %>% mutate(
  Afford4 = rowMeans(across(c(S1,S2,S3,S4)), na.rm=TRUE),
  SubjectID = as.factor(SubjectID),
  WWR = as.factor(WWR),
  Complexity = as.factor(Complexity),
  ExperienceGroup = as.factor(ExperienceGroup),
  SportFreqGroup = as.factor(SportFreqGroup),
  Repetition = as.factor(Repetition),
  Position = as.factor(Position)
)

# model
form <- Afford4 ~ Complexity + WWR + ExperienceGroup + SportFreqGroup + Repetition + Position + (1 + Complexity | SubjectID)
fit <- lmer(form, data=x, REML=FALSE)

# fixed effects table
fixef_tab <- broom.mixed::tidy(fit, effects="fixed", conf.int=TRUE, conf.level=0.95)
write_csv(fixef_tab, file.path(out_dir, "fixed_effects_afford4.csv"))

# model summary (text)
out_txt <- capture.output(summary(fit))
writeLines(out_txt, file.path(out_dir, "lmer_summary_afford4.txt"))

# emmeans: simple effects of Complexity within each WWR
emm <- emmeans(fit, ~ Complexity | WWR)
contr <- contrast(emm, method="revpairwise")  # C1 - C0 depending on factor coding
padj <- opt$`p-adjust`
if (tolower(padj) != "none") {
  contr <- summary(contr, infer=c(TRUE, TRUE), adjust=padj)
} else {
  contr <- summary(contr, infer=c(TRUE, TRUE), adjust="none")
}

# normalize output columns
contr_df <- as.data.frame(contr)
write_csv(contr_df, file.path(out_dir, "simple_effects_complexity_by_wwr_afford4.csv"))

# metadata json
meta <- list(
  dv="Afford4",
  formula=deparse(form),
  df_method=df_method,
  p_adjust=padj,
  n_rows=nrow(x),
  n_subjects=length(unique(x$SubjectID))
)
writeLines(jsonlite::toJSON(meta, auto_unbox=TRUE, pretty=TRUE), file.path(out_dir, "r_model_meta.json"))

cat(jsonlite::toJSON(list(out_dir=out_dir, long_csv=long_csv, outputs=c(
  "fixed_effects_afford4.csv",
  "lmer_summary_afford4.txt",
  "simple_effects_complexity_by_wwr_afford4.csv",
  "r_model_meta.json"
)), auto_unbox=TRUE))
