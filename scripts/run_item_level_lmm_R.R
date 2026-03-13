#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(optparse)
  library(readr)
  library(dplyr)
  library(tidyr)
  library(stringr)
  library(lme4)
  library(lmerTest)
  library(emmeans)
  library(jsonlite)
})

sig_tier <- function(p) {
  if (is.na(p)) return("")
  if (p < 0.001) return("***")
  if (p < 0.01) return("**")
  if (p < 0.05) return("*")
  ""
}

fmt_num <- function(x, digits = 4) {
  ifelse(is.na(x), NA_character_, format(round(x, digits), nsmall = digits, trim = TRUE))
}

extract_random_effects <- function(fit, dv) {
  vc <- as.data.frame(VarCorr(fit))
  if (nrow(vc) == 0) return(data.frame())
  vc %>%
    transmute(
      DV = dv,
      grp = .data$grp,
      var1 = .data$var1,
      var2 = if ("var2" %in% names(vc)) .data$var2 else NA_character_,
      vcov = .data$vcov,
      sdcor = .data$sdcor
    )
}

extract_fixed_effects <- function(fit, dv, df_method) {
  sm <- summary(fit, ddf = df_method)
  cf <- as.data.frame(sm$coefficients)
  cf$Term <- rownames(cf)
  rownames(cf) <- NULL
  names(cf) <- make.names(names(cf))

  ci <- try(confint(fit, method = "Wald"), silent = TRUE)
  ci_df <- data.frame(Term = character(), CI_low = numeric(), CI_high = numeric())
  if (!inherits(ci, "try-error")) {
    ci_df <- as.data.frame(ci)
    ci_df$Term <- rownames(ci_df)
    rownames(ci_df) <- NULL
    names(ci_df) <- c("CI_low", "CI_high", "Term")
  }

  pcol <- grep("^Pr", names(cf), value = TRUE)
  if (length(pcol) == 0) stop("No p column found in summary coefficients")

  cf %>%
    transmute(
      DV = dv,
      Term = .data$Term,
      Estimate = .data$Estimate,
      SE = .data$Std..Error,
      df = if ("df" %in% names(cf)) .data$df else NA_real_,
      statistic = if ("t.value" %in% names(cf)) .data$t.value else if ("z.value" %in% names(cf)) .data$z.value else NA_real_,
      p = .data[[pcol[1]]]
    ) %>%
    left_join(ci_df, by = "Term") %>%
    mutate(Sig = vapply(.data$p, sig_tier, character(1)))
}

extract_type3 <- function(fit, dv, formula_txt, df_method, requested_re, used_re, fit_method, n_rows, n_subjects) {
  a3 <- anova(fit, type = 3, ddf = df_method)
  a3_df <- as.data.frame(a3)
  a3_df$Effect <- rownames(a3_df)
  rownames(a3_df) <- NULL
  names(a3_df) <- make.names(names(a3_df))
  fcol <- intersect(c("F.value", "Chisq"), names(a3_df))
  pcol <- grep("^Pr", names(a3_df), value = TRUE)
  num_df_col <- intersect(c("NumDF", "npar"), names(a3_df))
  den_df_col <- intersect(c("DenDF", "ddf"), names(a3_df))
  ss_col <- intersect(c("Sum.Sq", "Sum.Sq.", "SSn"), names(a3_df))
  ms_col <- intersect(c("Mean.Sq", "Mean.Sq."), names(a3_df))

  out <- a3_df %>%
    transmute(
      DV = dv,
      Formula = formula_txt,
      Effect = .data$Effect,
      NumDF = if (length(num_df_col) > 0) .data[[num_df_col[1]]] else NA_real_,
      DenDF = if (length(den_df_col) > 0) .data[[den_df_col[1]]] else NA_real_,
      F_value = if (length(fcol) > 0) .data[[fcol[1]]] else NA_real_,
      p = if (length(pcol) > 0) .data[[pcol[1]]] else NA_real_,
      SumSq = if (length(ss_col) > 0) .data[[ss_col[1]]] else NA_real_,
      MeanSq = if (length(ms_col) > 0) .data[[ms_col[1]]] else NA_real_,
      requested_random = requested_re,
      used_random = used_re,
      fit_method = fit_method,
      n_rows = n_rows,
      n_subjects = n_subjects
    ) %>%
    mutate(Sig = vapply(.data$p, sig_tier, character(1)))
  out
}

fit_with_fallback <- function(formula_txt, dat, df_method) {
  attempts <- list(
    list(method = "bobyqa", re = "(1 + Complexity | SubjectID)"),
    list(method = "Nelder_Mead", re = "(1 + Complexity | SubjectID)"),
    list(method = "bobyqa", re = "(1 | SubjectID)"),
    list(method = "Nelder_Mead", re = "(1 | SubjectID)")
  )
  last_err <- NULL
  for (a in attempts) {
    full_formula <- paste0(formula_txt, " + ", a$re)
    fit <- try(
      lmer(
        as.formula(full_formula),
        data = dat,
        REML = FALSE,
        control = lmerControl(optimizer = a$method, calc.derivs = FALSE)
      ),
      silent = TRUE
    )
    if (!inherits(fit, "try-error")) {
      return(list(fit = fit, formula = full_formula, re = a$re, method = a$method))
    }
    last_err <- as.character(fit)
  }
  stop(last_err)
}

make_emmeans_outputs <- function(fit, dv, sig_effects, p_adjust) {
  emm_rows <- list()
  pair_rows <- list()

  add_emm_pair <- function(spec_label, emm_obj, pair_obj) {
    emm_df <- as.data.frame(summary(emm_obj, infer = c(TRUE, TRUE)))
    emm_df$DV <- dv
    emm_df$Spec <- spec_label
    emm_rows[[length(emm_rows) + 1]] <<- emm_df

    pair_df <- as.data.frame(summary(pair_obj, infer = c(TRUE, TRUE), adjust = p_adjust))
    pair_df$DV <- dv
    pair_df$Spec <- spec_label
    pair_df$Sig <- vapply(pair_df$p.value, sig_tier, character(1))
    pair_rows[[length(pair_rows) + 1]] <<- pair_df
  }

  if ("WWR" %in% sig_effects) {
    emm <- emmeans(fit, ~ WWR)
    add_emm_pair("WWR_main", emm, pairs(emm))
  }
  if ("Complexity" %in% sig_effects) {
    emm <- emmeans(fit, ~ Complexity)
    add_emm_pair("Complexity_main", emm, pairs(emm))
  }
  if ("ExperienceGroup" %in% sig_effects) {
    emm <- emmeans(fit, ~ ExperienceGroup)
    add_emm_pair("ExperienceGroup_main", emm, pairs(emm))
  }
  if ("WWR:Complexity" %in% sig_effects) {
    emm1 <- emmeans(fit, ~ WWR | Complexity)
    add_emm_pair("WWR_within_Complexity", emm1, pairs(emm1))
    emm2 <- emmeans(fit, ~ Complexity | WWR)
    add_emm_pair("Complexity_within_WWR", emm2, pairs(emm2))
  }
  if ("WWR:ExperienceGroup" %in% sig_effects) {
    emm1 <- emmeans(fit, ~ WWR | ExperienceGroup)
    add_emm_pair("WWR_within_ExperienceGroup", emm1, pairs(emm1))
    emm2 <- emmeans(fit, ~ ExperienceGroup | WWR)
    add_emm_pair("ExperienceGroup_within_WWR", emm2, pairs(emm2))
  }
  if ("Complexity:ExperienceGroup" %in% sig_effects) {
    emm1 <- emmeans(fit, ~ Complexity | ExperienceGroup)
    add_emm_pair("Complexity_within_ExperienceGroup", emm1, pairs(emm1))
    emm2 <- emmeans(fit, ~ ExperienceGroup | Complexity)
    add_emm_pair("ExperienceGroup_within_Complexity", emm2, pairs(emm2))
  }
  if ("WWR:Complexity:ExperienceGroup" %in% sig_effects) {
    emm1 <- emmeans(fit, ~ WWR | Complexity * ExperienceGroup)
    add_emm_pair("WWR_within_Complexity_by_ExperienceGroup", emm1, pairs(emm1))
    emm2 <- emmeans(fit, ~ Complexity | WWR * ExperienceGroup)
    add_emm_pair("Complexity_within_WWR_by_ExperienceGroup", emm2, pairs(emm2))
    emm3 <- emmeans(fit, ~ ExperienceGroup | WWR * Complexity)
    add_emm_pair("ExperienceGroup_within_WWR_by_Complexity", emm3, pairs(emm3))
  }

  list(
    emmeans = bind_rows(emm_rows),
    pairwise = bind_rows(pair_rows)
  )
}

write_report_zh <- function(out_path, summary_df, fdr_df) {
  lines <- c(
    "# 逐题 / 逐维度 LMM 结果汇总（自动生成）",
    "",
    "固定效应统一为：WWR、Complexity、ExperienceGroup，以及所有二阶 / 三阶交互；随机部分默认尝试 `(1 + Complexity | SubjectID)`，失败时回退到 `(1 | SubjectID)`。",
    "估计方法：ML；Type III fixed effects 使用 lmerTest；显著项 follow-up 使用 estimated marginal means + pairwise comparisons。",
    ""
  )

  if (nrow(summary_df) > 0) {
    lines <- c(lines, "## 每个因变量的模型状态", "")
    for (i in seq_len(nrow(summary_df))) {
      r <- summary_df[i, ]
      lines <- c(lines, sprintf(
        "- %s：status=%s；subjects=%s；rows=%s；random=%s；AIC=%s；BIC=%s；-2LL=%s",
        r$DV, r$Status, r$n_subjects, r$n_rows, r$used_random,
        fmt_num(r$AIC), fmt_num(r$BIC), fmt_num(r$minus2LL)
      ))
    }
    lines <- c(lines, "")
  }

  if (nrow(fdr_df) > 0) {
    sig_df <- fdr_df %>% filter(!is.na(.data$p_fdr) & .data$p_fdr < 0.05)
    lines <- c(lines, "## FDR 后仍显著的 fixed effects", "")
    if (nrow(sig_df) == 0) {
      lines <- c(lines, "- 当前没有在 FDR 校正后仍显著的效应。", "")
    } else {
      for (i in seq_len(nrow(sig_df))) {
        r <- sig_df[i, ]
        lines <- c(lines, sprintf(
          "- %s | %s：F(%s, %s) = %s, p = %s, FDR p = %s",
          r$DV, r$Effect, fmt_num(r$NumDF, 2), fmt_num(r$DenDF, 2), fmt_num(r$F_value, 3), fmt_num(r$p, 4), fmt_num(r$p_fdr, 4)
        ))
      }
      lines <- c(lines, "")
    }
  }

  writeLines(lines, out_path)
}

option_list <- list(
  make_option(c("--long-csv"), type = "character"),
  make_option(c("--out-dir"), type = "character", default = "results/significance/item_level_lmm"),
  make_option(c("--exclude-subjects"), type = "character", default = ""),
  make_option(c("--p-adjust"), type = "character", default = "fdr"),
  make_option(c("--df-method"), type = "character", default = "Satterthwaite")
)
opt <- parse_args(OptionParser(option_list = option_list))
if (is.null(opt$`long-csv`)) stop("--long-csv is required")

out_dir <- opt$`out-dir`
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
for (subdir in c("csv", "md", "json")) dir.create(file.path(out_dir, subdir), recursive = TRUE, showWarnings = FALSE)

x <- read_csv(opt$`long-csv`, show_col_types = FALSE)
if (nzchar(opt$`exclude-subjects`) && "SubjectID" %in% names(x)) {
  ids <- trimws(unlist(strsplit(as.character(opt$`exclude-subjects`), ",", fixed = TRUE)))
  ids <- ids[nzchar(ids)]
  if (length(ids) > 0) x <- x %>% filter(!(as.character(.data$SubjectID) %in% ids))
}

req <- c("SubjectID", "WWR", "Complexity", "ExperienceGroup")
miss <- setdiff(req, names(x))
if (length(miss) > 0) stop(paste("Missing required columns:", paste(miss, collapse = ", ")))

x <- x %>% mutate(
  SubjectID = as.factor(.data$SubjectID),
  WWR = as.factor(.data$WWR),
  Complexity = as.factor(.data$Complexity),
  ExperienceGroup = as.factor(.data$ExperienceGroup)
)

all_dvs <- c(sprintf("S%d", 1:5), sprintf("B%d", 1:3), sprintf("IPQ%d", 1:6), "IPQ_mean")
dvs <- intersect(all_dvs, names(x))

status_rows <- list()
desc_rows <- list()
type3_rows <- list()
fixed_rows <- list()
random_rows <- list()
fit_rows <- list()
emm_rows <- list()
pair_rows <- list()

for (dv in dvs) {
  dat <- x %>% filter(!is.na(.data[[dv]]))
  n_subjects <- dplyr::n_distinct(dat$SubjectID)
  n_rows <- nrow(dat)

  if (n_rows == 0 || n_subjects < 3) {
    status_rows[[length(status_rows) + 1]] <- data.frame(DV = dv, Status = "skipped_insufficient_data", n_rows = n_rows, n_subjects = n_subjects)
    next
  }

  desc_rows[[length(desc_rows) + 1]] <- dat %>%
    group_by(.data$WWR, .data$Complexity, .data$ExperienceGroup) %>%
    summarise(DV = dv, n = dplyr::n(), mean = mean(.data[[dv]], na.rm = TRUE), sd = sd(.data[[dv]], na.rm = TRUE), .groups = "drop") %>%
    relocate(.data$DV)

  rhs <- paste("WWR * Complexity * ExperienceGroup")
  fit_obj <- try(fit_with_fallback(formula_txt = paste0(dv, " ~ ", rhs), dat = dat, df_method = opt$`df-method`), silent = TRUE)
  if (inherits(fit_obj, "try-error")) {
    status_rows[[length(status_rows) + 1]] <- data.frame(DV = dv, Status = "fit_failed", Reason = as.character(fit_obj), n_rows = n_rows, n_subjects = n_subjects)
    next
  }

  fit <- fit_obj$fit
  full_formula <- fit_obj$formula
  used_re <- fit_obj$re
  fit_method <- fit_obj$method

  status_rows[[length(status_rows) + 1]] <- data.frame(
    DV = dv,
    Status = "ok",
    Formula = full_formula,
    requested_random = "(1 + Complexity | SubjectID)",
    used_random = used_re,
    fit_method = fit_method,
    n_rows = n_rows,
    n_subjects = n_subjects
  )

  type3_df <- try(extract_type3(fit, dv, full_formula, opt$`df-method`, "(1 + Complexity | SubjectID)", used_re, fit_method, n_rows, n_subjects), silent = TRUE)
  if (!inherits(type3_df, "try-error")) {
    type3_rows[[length(type3_rows) + 1]] <- type3_df
    sig_effects <- type3_df %>% filter(!is.na(.data$p) & .data$p < 0.05) %>% pull(.data$Effect) %>% as.character()
    emm_out <- try(make_emmeans_outputs(fit, dv, sig_effects, opt$`p-adjust`), silent = TRUE)
    if (!inherits(emm_out, "try-error")) {
      if (nrow(emm_out$emmeans) > 0) emm_rows[[length(emm_rows) + 1]] <- emm_out$emmeans
      if (nrow(emm_out$pairwise) > 0) pair_rows[[length(pair_rows) + 1]] <- emm_out$pairwise
    }
  }

  fixed_df <- try(extract_fixed_effects(fit, dv, opt$`df-method`), silent = TRUE)
  if (!inherits(fixed_df, "try-error")) fixed_rows[[length(fixed_rows) + 1]] <- fixed_df

  random_df <- try(extract_random_effects(fit, dv), silent = TRUE)
  if (!inherits(random_df, "try-error") && nrow(random_df) > 0) random_rows[[length(random_rows) + 1]] <- random_df

  fit_rows[[length(fit_rows) + 1]] <- data.frame(
    DV = dv,
    Formula = full_formula,
    requested_random = "(1 + Complexity | SubjectID)",
    used_random = used_re,
    fit_method = fit_method,
    n_rows = n_rows,
    n_subjects = n_subjects,
    AIC = AIC(fit),
    BIC = BIC(fit),
    logLik = as.numeric(logLik(fit)),
    minus2LL = -2 * as.numeric(logLik(fit))
  )
}

status_df <- bind_rows(status_rows)
desc_df <- bind_rows(desc_rows)
type3_df <- bind_rows(type3_rows)
fixed_df <- bind_rows(fixed_rows)
random_df <- bind_rows(random_rows)
fit_df <- bind_rows(fit_rows)
emm_df <- bind_rows(emm_rows)
pair_df <- bind_rows(pair_rows)

fdr_df <- type3_df
if (nrow(fdr_df) > 0) {
  keep_mask <- !is.na(fdr_df$p)
  fdr_df$p_fdr <- NA_real_
  if (sum(keep_mask) > 0) {
    fdr_df$p_fdr[keep_mask] <- p.adjust(fdr_df$p[keep_mask], method = "fdr")
  }
  fdr_df$Sig_FDR <- vapply(fdr_df$p_fdr, sig_tier, character(1))
}

summary_df <- status_df %>%
  left_join(fit_df %>% select(.data$DV, .data$AIC, .data$BIC, .data$logLik, .data$minus2LL, .data$used_random), by = "DV")

write_csv(status_df, file.path(out_dir, "csv", "item_level_lmm_model_status.csv"))
write_csv(desc_df, file.path(out_dir, "csv", "item_level_lmm_descriptives.csv"))
write_csv(type3_df, file.path(out_dir, "csv", "item_level_lmm_type3_fixed_effects.csv"))
write_csv(fixed_df, file.path(out_dir, "csv", "item_level_lmm_fixed_effect_estimates.csv"))
write_csv(random_df, file.path(out_dir, "csv", "item_level_lmm_random_effects.csv"))
write_csv(fit_df, file.path(out_dir, "csv", "item_level_lmm_fit_indices.csv"))
write_csv(emm_df, file.path(out_dir, "csv", "item_level_lmm_emmeans.csv"))
write_csv(pair_df, file.path(out_dir, "csv", "item_level_lmm_pairwise.csv"))
write_csv(fdr_df, file.path(out_dir, "csv", "item_level_lmm_type3_fixed_effects_fdr.csv"))

write_report_zh(file.path(out_dir, "md", "item_level_lmm_report_zh.md"), summary_df, fdr_df)

payload <- list(
  task = "item_level_lmm",
  dv_count = length(dvs),
  outputs = c(
    "csv/item_level_lmm_model_status.csv",
    "csv/item_level_lmm_descriptives.csv",
    "csv/item_level_lmm_type3_fixed_effects.csv",
    "csv/item_level_lmm_type3_fixed_effects_fdr.csv",
    "csv/item_level_lmm_fixed_effect_estimates.csv",
    "csv/item_level_lmm_random_effects.csv",
    "csv/item_level_lmm_fit_indices.csv",
    "csv/item_level_lmm_emmeans.csv",
    "csv/item_level_lmm_pairwise.csv",
    "md/item_level_lmm_report_zh.md"
  ),
  modeling_note = "Each DV is fit with the same fixed-effect structure: WWR * Complexity * ExperienceGroup.",
  p_adjust = opt$`p-adjust`,
  df_method = opt$`df-method`
)
writeLines(toJSON(payload, auto_unbox = TRUE, pretty = TRUE), file.path(out_dir, "json", "item_level_lmm_summary.json"))
cat(toJSON(payload, auto_unbox = TRUE))
