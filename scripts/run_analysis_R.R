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

sig_tier <- function(p) {
  if (is.na(p)) return("")
  if (p < 0.001) return("***")
  if (p < 0.01) return("**")
  if (p < 0.05) return("*")
  ""
}

plot_eta2_bar <- function(df, out_path, title_txt) {
  if (is.null(df) || nrow(df) == 0) return(FALSE)
  if (!("term" %in% names(df)) || !("eta2_partial" %in% names(df))) return(FALSE)

  z <- df %>%
    filter(!is.na(.data$eta2_partial)) %>%
    mutate(
      term = as.character(.data$term),
      magnitude = if ("magnitude" %in% names(df)) as.character(.data$magnitude) else "",
      label = sprintf("%.3f", .data$eta2_partial)
    ) %>%
    arrange(.data$eta2_partial)

  if (nrow(z) == 0) return(FALSE)

  cols <- c(
    very_small = "#BFC7D5",
    small = "#9DB7D5",
    medium = "#5B8CC0",
    large = "#2F5D8A"
  )
  fill_cols <- unname(cols[ifelse(z$magnitude %in% names(cols), z$magnitude, "small")])

  png(out_path, width = 2400, height = 1400, res = 300, bg = "white")
  old_par <- par(no.readonly = TRUE)
  on.exit({par(old_par); dev.off()}, add = TRUE)

  par(mar = c(5.2, 10.5, 3.2, 1.2), family = "sans")
  bp <- barplot(
    z$eta2_partial,
    names.arg = z$term,
    horiz = TRUE,
    las = 1,
    col = fill_cols,
    border = NA,
    xlim = c(0, max(z$eta2_partial, na.rm = TRUE) * 1.18),
    xlab = expression(paste("Partial ", eta^2)),
    main = title_txt,
    cex.names = 0.95,
    cex.lab = 1.05,
    cex.main = 1.05
  )

  abline(v = c(0.01, 0.06, 0.14), col = c("#C7CDD6", "#9AA7B7", "#6B7C93"), lty = c(3, 2, 2), lwd = c(1, 1.2, 1.2))
  text(x = z$eta2_partial, y = bp, labels = z$label, pos = 4, cex = 0.9, col = "#1F2D3D", xpd = TRUE)
  legend(
    "bottomright",
    legend = c("very small (<0.01)", "small (0.01-0.06)", "medium (0.06-0.14)", "large (>=0.14)"),
    fill = cols[c("very_small", "small", "medium", "large")],
    bty = "n",
    cex = 0.9
  )

  TRUE
}

# optional packages (journal-friendly extras)
.has_performance <- requireNamespace("performance", quietly = TRUE)
.has_effectsize <- requireNamespace("effectsize", quietly = TRUE)

option_list <- list(
  make_option(c("--long-csv"), type="character", help="Path to results/long/long_format.csv"),
  make_option(c("--out-dir"), type="character", default="results/r_model", help="Output directory"),
  make_option(c("--df-method"), type="character", default="Satterthwaite", help="Satterthwaite|Kenward-Roger"),
  make_option(c("--p-adjust"), type="character", default="Holm", help="Holm|bonferroni|fdr|none"),
  make_option(c("--reml"), type="character", default="auto", help="auto|TRUE|FALSE. Note: Kenward-Roger requires REML=TRUE")
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

# REML setting
reml_opt <- tolower(as.character(opt$reml)[1])
if (reml_opt == "auto") {
  reml_flag <- if (use_kr) TRUE else FALSE
} else if (reml_opt %in% c("true","t","1")) {
  reml_flag <- TRUE
} else if (reml_opt %in% c("false","f","0")) {
  reml_flag <- FALSE
} else {
  stop("Invalid --reml. Use auto|TRUE|FALSE")
}

if (use_kr && !reml_flag) {
  stop("Kenward-Roger requires REML=TRUE. Please run with --reml TRUE (or --reml auto).")
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

# build Afford4 with explicit missing-item rule
# default: require >=3/4 valid items; otherwise set NA
min_items <- 3
x <- x %>% mutate(
  Afford4_n_valid = rowSums(!is.na(across(c(S1,S2,S3,S4)))),
  Afford4_lenient = rowMeans(across(c(S1,S2,S3,S4)), na.rm=TRUE),
  Afford4 = ifelse(Afford4_n_valid >= min_items, Afford4_lenient, NA),
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
fit <- lmer(form, data=x, REML=reml_flag)

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
# make names consistent across R versions/locales
names(coef_mat) <- make.names(names(coef_mat))

# Wald CI for fixed effects (fast)
ci <- suppressMessages(confint(fit, method = "Wald"))
ci <- as.data.frame(ci)
ci$term <- rownames(ci)
rownames(ci) <- NULL
names(ci) <- c("conf_low", "conf_high", "term")

# normalize column names from lmerTest summary
# expected after make.names(): Estimate, Std..Error, df, t.value, Pr...t..
need <- c("Estimate","Std..Error","df","t.value")
missing_cols <- setdiff(need, names(coef_mat))
if (length(missing_cols) > 0) stop(paste("Unexpected coefficient columns:", paste(missing_cols, collapse=", ")))

pcol <- grep("^Pr", names(coef_mat), value = TRUE)
if (length(pcol) == 0) stop("p-value column not found in summary coefficients")

fixef_tab <- coef_mat %>%
  transmute(
    term = term,
    estimate = .data$Estimate,
    std.error = .data$Std..Error,
    df = .data$df,
    statistic = .data$t.value,
    p.value = .data[[pcol[1]]]
  ) %>%
  left_join(ci %>% select(term, conf_low, conf_high), by = "term")

write_csv(fixef_tab, file.path(out_dir, "fixed_effects_afford4.csv"))

# Effect sizes (journal-friendly)
# 1) Standardized fixed-effect parameters
if (.has_effectsize) {
  stdp <- try(effectsize::standardize_parameters(fit, method = "refit"), silent = TRUE)
  if (!inherits(stdp, "try-error")) {
    write_csv(as.data.frame(stdp), file.path(out_dir, "effectsize_standardized_parameters_afford4.csv"))
  }
}

# 2) Partial eta^2 from Type III ANOVA table (lmerTest)
# Note: This is a common journal-friendly summary; interpret with care.
eta_status <- list(ok = FALSE, reason = NULL)
a3 <- try(lmerTest::anova(fit, type = 3, ddf = if (use_kr) "Kenward-Roger" else "Satterthwaite"), silent = TRUE)
if (!inherits(a3, "try-error")) {
  write_csv(as.data.frame(a3), file.path(out_dir, "anova_type3_afford4.csv"))

  if (.has_effectsize) {
    et <- try(effectsize::eta_squared(a3, partial = TRUE), silent = TRUE)
    if (!inherits(et, "try-error")) {
      et_df <- as.data.frame(et)
      names(et_df) <- make.names(names(et_df))

      if ("Eta2_partial" %in% names(et_df)) {
        et_df <- et_df %>% mutate(
          effect_size_magnitude = dplyr::case_when(
            Eta2_partial < 0.01 ~ "very_small",
            Eta2_partial < 0.06 ~ "small",
            Eta2_partial < 0.14 ~ "medium",
            TRUE ~ "large"
          )
        )
      }

      write_csv(et_df, file.path(out_dir, "effectsize_eta_squared_partial_afford4.csv"))

      if (all(c("Parameter", "Eta2_partial") %in% names(et_df))) {
        eta_summary <- et_df %>%
          transmute(
            term = as.character(.data$Parameter),
            eta2_partial = .data$Eta2_partial,
            magnitude = if ("effect_size_magnitude" %in% names(et_df)) .data$effect_size_magnitude else NA_character_
          )

        if ("term" %in% names(fixef_tab) && "p.value" %in% names(fixef_tab)) {
          p_lookup <- fixef_tab %>%
            filter(.data$term != "(Intercept)") %>%
            transmute(term = as.character(.data$term), p_value = .data$p.value, sig = vapply(.data$p.value, sig_tier, character(1)))
          eta_summary <- eta_summary %>% left_join(p_lookup, by = "term")
        }

        write_csv(eta_summary, file.path(out_dir, "effectsize_eta_squared_partial_summary_afford4.csv"))
        plot_eta2_bar(
          eta_summary,
          file.path(out_dir, "effectsize_eta_squared_partial_afford4.png"),
          "Effect sizes of fixed terms on Afford4"
        )
      }

      eta_status$ok <- TRUE
    } else {
      eta_status$reason <- paste("effectsize::eta_squared failed:", as.character(et))
    }
  } else {
    eta_status$reason <- "R package 'effectsize' is not installed; partial eta^2 not exported."
  }
} else {
  eta_status$reason <- paste("lmerTest::anova(type=3) failed:", as.character(a3))
}

if (!isTRUE(eta_status$ok)) {
  writeLines(
    c(
      "partial eta^2 export not available for this run.",
      paste("reason:", if (is.null(eta_status$reason) || is.na(eta_status$reason) || eta_status$reason == "") "unknown" else eta_status$reason)
    ),
    file.path(out_dir, "effectsize_eta_squared_partial_status.txt")
  )
}

# model summary (text)
out_txt <- capture.output(sum_fit)
writeLines(out_txt, file.path(out_dir, "lmer_summary_afford4.txt"))

padj <- opt$`p-adjust`

# emmeans helpers
write_emm_pairs <- function(obj, out_path, extra_cols=list()) {
  s <- summary(obj, infer=c(TRUE, TRUE), adjust=ifelse(tolower(padj)!="none", padj, "none"))
  df <- as.data.frame(s)
  for (nm in names(extra_cols)) {
    df[[nm]] <- extra_cols[[nm]]
  }
  write_csv(df, out_path)
}

# 1) Complexity simple effects within each WWR (C1 - C0)
emm_c_by_w <- emmeans(fit, ~ Complexity | WWR)
contr_c_by_w <- contrast(emm_c_by_w, method="revpairwise")
contr_df <- as.data.frame(summary(contr_c_by_w, infer=c(TRUE, TRUE), adjust=ifelse(tolower(padj)!="none", padj, "none")))
write_csv(contr_df, file.path(out_dir, "simple_effects_complexity_by_wwr_afford4.csv"))

# 2) Journal-style emmeans pairwise tables (Holm by default)
# WWR pairwise within each Complexity
emm_w_by_c <- emmeans(fit, ~ WWR | Complexity)
pairs_w_by_c <- pairs(emm_w_by_c)
write_emm_pairs(pairs_w_by_c, file.path(out_dir, "emmeans_pairs_wwr_within_complexity_afford4.csv"))

# Complexity pairwise within each WWR (redundant with simple_effects, but in standard emmeans format)
pairs_c_by_w <- pairs(emm_c_by_w)
write_emm_pairs(pairs_c_by_w, file.path(out_dir, "emmeans_pairs_complexity_within_wwr_afford4.csv"))

# Main-effect pairwise tables (collapsed over other fixed effects)
# (Binary groups: still exported for paper-ready reporting)
emm_wwr <- emmeans(fit, ~ WWR)
write_emm_pairs(pairs(emm_wwr), file.path(out_dir, "emmeans_pairs_wwr_main_afford4.csv"))

emm_exp <- emmeans(fit, ~ ExperienceGroup)
write_emm_pairs(pairs(emm_exp), file.path(out_dir, "emmeans_pairs_experiencegroup_main_afford4.csv"))

emm_sf <- emmeans(fit, ~ SportFreqGroup)
write_emm_pairs(pairs(emm_sf), file.path(out_dir, "emmeans_pairs_sportfreqgroup_main_afford4.csv"))

# metadata json
meta <- list(
  dv="Afford4",
  formula=deparse(form),
  df_method=df_method,
  p_adjust=padj,
  reml=reml_flag,
  afford4_min_items=min_items,
  n_rows=nrow(x),
  n_subjects=length(unique(x$SubjectID))
)
# Add journal-friendly fit indices
meta$aic <- AIC(fit)
meta$bic <- BIC(fit)
meta$logLik <- as.numeric(logLik(fit))

# Nakagawa R^2 (marginal/conditional) if available
if (.has_performance) {
  r2 <- try(performance::r2_nakagawa(fit), silent = TRUE)
  if (!inherits(r2, "try-error")) {
    # typical columns: R2_marginal, R2_conditional
    write_csv(as.data.frame(r2), file.path(out_dir, "r2_nakagawa_afford4.csv"))
    meta$r2_nakagawa <- as.list(as.data.frame(r2)[1, , drop=TRUE])
  }
}

meta$eta_squared_partial_available <- isTRUE(eta_status$ok)
meta$eta_squared_partial_reason <- if (!isTRUE(eta_status$ok)) eta_status$reason else NULL

writeLines(jsonlite::toJSON(meta, auto_unbox=TRUE, pretty=TRUE), file.path(out_dir, "r_model_meta.json"))

outs <- c(
  "fixed_effects_afford4.csv",
  "lmer_summary_afford4.txt",
  "simple_effects_complexity_by_wwr_afford4.csv",
  "emmeans_pairs_wwr_within_complexity_afford4.csv",
  "emmeans_pairs_complexity_within_wwr_afford4.csv",
  "emmeans_pairs_wwr_main_afford4.csv",
  "emmeans_pairs_experiencegroup_main_afford4.csv",
  "emmeans_pairs_sportfreqgroup_main_afford4.csv",
  "r_model_meta.json"
)
if (file.exists(file.path(out_dir, "r2_nakagawa_afford4.csv"))) outs <- c(outs, "r2_nakagawa_afford4.csv")
if (file.exists(file.path(out_dir, "anova_type3_afford4.csv"))) outs <- c(outs, "anova_type3_afford4.csv")
if (file.exists(file.path(out_dir, "effectsize_standardized_parameters_afford4.csv"))) outs <- c(outs, "effectsize_standardized_parameters_afford4.csv")
if (file.exists(file.path(out_dir, "effectsize_eta_squared_partial_afford4.csv"))) outs <- c(outs, "effectsize_eta_squared_partial_afford4.csv")
if (file.exists(file.path(out_dir, "effectsize_eta_squared_partial_summary_afford4.csv"))) outs <- c(outs, "effectsize_eta_squared_partial_summary_afford4.csv")
if (file.exists(file.path(out_dir, "effectsize_eta_squared_partial_afford4.png"))) outs <- c(outs, "effectsize_eta_squared_partial_afford4.png")
if (file.exists(file.path(out_dir, "effectsize_eta_squared_partial_status.txt"))) outs <- c(outs, "effectsize_eta_squared_partial_status.txt")

cat(jsonlite::toJSON(list(out_dir=out_dir, long_csv=long_csv, outputs=outs), auto_unbox=TRUE))
