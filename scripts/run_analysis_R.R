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
df_method_norm <- tolower(as.character(df_method)[1])
use_kr <- df_method_norm %in% c("kenward-roger", "kenwardroger", "kr")
if (use_kr) {
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

# Use lmerTest for df approximation
# - Satterthwaite: default
# - Kenward-Roger: requires pbkrtest
# NOTE: Some lmerTest versions do not export summary() as lmerTest::summary.
# Use the generic summary() (lmerTest provides methods + ddf handling).
if (use_kr) {
  sum_fit <- summary(fit, ddf = "Kenward-Roger")
  emmeans::emm_options(lmer.df = "kenward-roger")
} else {
  sum_fit <- summary(fit, ddf = "Satterthwaite")
  emmeans::emm_options(lmer.df = "satterthwaite")
}

# fixed effects table (explicitly derived from summary for correct df-method)
coef_mat <- as.data.frame(sum_fit$coefficients)
coef_mat$term <- rownames(coef_mat)
rownames(coef_mat) <- NULL
names(coef_mat) <- gsub(" ", "_", names(coef_mat))

# Wald CI for fixed effects (fast)
ci <- suppressMessages(confint(fit, method = "Wald"))
ci <- as.data.frame(ci)
ci$term <- rownames(ci)
rownames(ci) <- NULL
names(ci) <- c("conf_low", "conf_high", "term")

# normalize column names from lmerTest summary
# expected: Estimate, Std. Error, df, t value, Pr(>|t|)
fixef_tab <- coef_mat %>%
  transmute(
    term = term,
    estimate = Estimate,
    std.error = Std._Error,
    df = df,
    statistic = t_value,
    p.value = Pr...t..
  ) %>%
  left_join(ci %>% filter(term %in% term) %>% select(term, conf_low, conf_high), by = "term")

write_csv(fixef_tab, file.path(out_dir, "fixed_effects_afford4.csv"))

# model summary (text)
out_txt <- capture.output(sum_fit)
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
