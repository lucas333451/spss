#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(optparse)
  library(readr)
  library(dplyr)
  library(stringr)
  library(lme4)
  library(lmerTest)
  library(emmeans)
  library(jsonlite)
})

.has_effectsize <- requireNamespace("effectsize", quietly = TRUE)
.has_pbkrtest <- requireNamespace("pbkrtest", quietly = TRUE)

S_DVS <- c("S1", "S2", "S3", "S4", "S5")
B_DVS <- c("B1", "B2", "B3")

sig_tier <- function(p) {
  if (is.na(p)) return("")
  if (p < 0.001) return("***")
  if (p < 0.01) return("**")
  if (p < 0.05) return("*")
  ""
}

eta_mag <- function(x) {
  if (is.na(x)) return(NA_character_)
  if (x < 0.01) return("very_small")
  if (x < 0.06) return("small")
  if (x < 0.14) return("medium")
  "large"
}

plot_eta2_bar <- function(df, out_path, title_txt, core_only = FALSE) {
  if (is.null(df) || nrow(df) == 0) return(FALSE)
  if (!("term" %in% names(df)) || !("eta2_partial" %in% names(df))) return(FALSE)
  core_terms <- c("WWR", "Complexity", "Group", "WWR×Complexity", "WWR×Group", "Complexity×Group", "3-way")

  z <- df %>%
    filter(!is.na(.data$eta2_partial)) %>%
    mutate(
      term = as.character(.data$term),
      magnitude = if ("magnitude" %in% names(df)) as.character(.data$magnitude) else "",
      sig = if ("sig" %in% names(df)) as.character(.data$sig) else "",
      label = ifelse(is.na(.data$sig) | .data$sig == "", sprintf("%.3f", .data$eta2_partial), paste0(sprintf("%.3f", .data$eta2_partial), .data$sig))
    )

  if (core_only) {
    z <- z %>% filter(.data$term %in% core_terms)
    z$term <- factor(z$term, levels = rev(core_terms[core_terms %in% z$term]))
    z <- z %>% arrange(.data$term)
  } else {
    z <- z %>% arrange(.data$eta2_partial)
  }
  if (nrow(z) == 0) return(FALSE)

  cols <- c(very_small = "#D9D4C7", small = "#AFC8C3", medium = "#6FA7A1", large = "#2F7C80")
  fill_cols <- unname(cols[ifelse(z$magnitude %in% names(cols), z$magnitude, "small")])

  png(out_path, width = if (core_only) 2200 else 2400, height = if (core_only) 1100 else 1400, res = 300, bg = "white")
  old_par <- par(no.readonly = TRUE)
  on.exit({par(old_par); dev.off()}, add = TRUE)

  par(mar = c(5.2, if (core_only) 7.8 else 10.5, 3.0, 1.2), family = "sans")
  xmax <- max(z$eta2_partial, na.rm = TRUE)
  bp <- barplot(
    z$eta2_partial,
    names.arg = z$term,
    horiz = TRUE,
    las = 1,
    col = fill_cols,
    border = NA,
    xlim = c(0, xmax * if (core_only) 1.12 else 1.18),
    xlab = expression(paste("Partial ", eta^2)),
    main = title_txt,
    cex.names = if (core_only) 1.0 else 0.95,
    cex.lab = 1.05,
    cex.main = 1.05
  )
  abline(v = c(0.01, 0.06, 0.14), col = c("#D8D3C8", "#A9B9B5", "#6FA7A1"), lty = c(3, 2, 2), lwd = c(1, 1.1, 1.1))
  text(x = z$eta2_partial, y = bp, labels = z$label, pos = 4, cex = 0.9, col = "#294246", xpd = TRUE)
  legend("bottomright", legend = c("very small (<0.01)", "small (0.01-0.06)", "medium (0.06-0.14)", "large (>=0.14)"), fill = cols[c("very_small", "small", "medium", "large")], bty = "n", cex = 0.88)
  TRUE
}

make_people_group4 <- function(df) {
  df %>% mutate(PeopleGroup4 = paste0(as.character(.data$ExperienceGroup), "__", as.character(.data$SportFreqGroup)))
}

exclude_subjects <- function(df, text) {
  if (is.null(text) || !nzchar(text) || !("SubjectID" %in% names(df))) return(df)
  ids <- trimws(unlist(strsplit(as.character(text), ",", fixed = TRUE)))
  ids <- ids[nzchar(ids)]
  if (length(ids) == 0) return(df)
  df %>% filter(!(as.character(.data$SubjectID) %in% ids))
}

bucket_term <- function(term, group_col) {
  t <- as.character(term)
  has_w <- grepl("WWR", t, fixed = TRUE)
  has_c <- grepl("Complexity", t, fixed = TRUE)
  has_g <- grepl(group_col, t, fixed = TRUE)
  if (has_w && has_c && has_g) return("3-way")
  if (has_w && has_c) return("WWR×Complexity")
  if (has_w && has_g) return("WWR×Group")
  if (has_c && has_g) return("Complexity×Group")
  if (has_w) return("WWR")
  if (has_c) return("Complexity")
  if (has_g) return("Group")
  NA_character_
}

extract_eta <- function(a3, dv, domain, model_name, group_col) {
  if (!.has_effectsize) return(data.frame())
  et <- try(effectsize::eta_squared(a3, partial = TRUE), silent = TRUE)
  if (inherits(et, "try-error")) return(data.frame())
  et_df <- as.data.frame(et)
  names(et_df) <- make.names(names(et_df))
  if (!("Parameter" %in% names(et_df)) || !("Eta2_partial" %in% names(et_df))) return(data.frame())
  et_df %>%
    transmute(
      Domain = domain,
      DV = dv,
      Model = model_name,
      term_raw = as.character(.data$Parameter),
      term = vapply(as.character(.data$Parameter), bucket_term, character(1), group_col = group_col),
      eta2_partial = .data$Eta2_partial,
      magnitude = vapply(.data$Eta2_partial, eta_mag, character(1))
    ) %>%
    filter(!is.na(.data$term))
}

run_one_model <- function(data, dv, domain, model_name, formula_txt, group_col, use_kr) {
  need <- c("SubjectID", "WWR", group_col, dv)
  if (grepl("Complexity", formula_txt, fixed = TRUE)) need <- c(need, "Complexity")
  sub <- data %>% filter(if_all(all_of(need), ~ !is.na(.x)))
  if (nrow(sub) == 0 || dplyr::n_distinct(sub$SubjectID) < 3) {
    return(list(status = data.frame(Domain=domain, DV=dv, Model=model_name, Formula=formula_txt, Status="skipped_insufficient_data", n_rows=nrow(sub), n_subjects=dplyr::n_distinct(sub$SubjectID), stringsAsFactors = FALSE), eta = data.frame()))
  }

  sub <- sub %>% mutate(SubjectID = as.factor(.data$SubjectID), WWR = as.factor(.data$WWR))
  sub[[group_col]] <- as.factor(sub[[group_col]])
  if ("Complexity" %in% names(sub)) sub$Complexity <- as.factor(sub$Complexity)

  fit <- try(lmer(as.formula(formula_txt), data = sub, REML = use_kr), silent = TRUE)
  if (inherits(fit, "try-error")) {
    return(list(status = data.frame(Domain=domain, DV=dv, Model=model_name, Formula=formula_txt, Status="failed", Reason=as.character(fit), n_rows=nrow(sub), n_subjects=dplyr::n_distinct(sub$SubjectID), stringsAsFactors = FALSE), eta = data.frame()))
  }

  a3 <- try(anova(fit, type = 3, ddf = if (use_kr) "Kenward-Roger" else "Satterthwaite"), silent = TRUE)
  if (inherits(a3, "try-error")) {
    a3 <- try(stats::anova(fit), silent = TRUE)
  }
  if (inherits(a3, "try-error")) {
    return(list(status = data.frame(Domain=domain, DV=dv, Model=model_name, Formula=formula_txt, Status="anova_failed", Reason=as.character(a3), n_rows=nrow(sub), n_subjects=dplyr::n_distinct(sub$SubjectID), stringsAsFactors = FALSE), eta = data.frame()))
  }

  an_df <- as.data.frame(a3)
  names(an_df) <- make.names(names(an_df))
  pcol <- intersect(c("Pr...F.", "Pr...Chisq."), names(an_df))
  if (length(pcol) == 0) pcol <- names(an_df)[grepl("^Pr", names(an_df))]
  eta_df <- extract_eta(a3, dv = dv, domain = domain, model_name = model_name, group_col = group_col)
  if (nrow(eta_df) > 0 && length(pcol) > 0) {
    p_lookup <- an_df
    p_lookup$term_raw <- rownames(an_df)
    p_lookup <- p_lookup %>% transmute(term_raw = .data$term_raw, p = .data[[pcol[1]]], sig = vapply(.data[[pcol[1]]], sig_tier, character(1)))
    eta_df <- eta_df %>% left_join(p_lookup, by = "term_raw")
  }

  anova_out <- an_df
  anova_out$term_raw <- rownames(an_df)
  anova_out <- anova_out %>% mutate(Domain=domain, DV=dv, Model=model_name, Formula=formula_txt)

  status <- data.frame(Domain=domain, DV=dv, Model=model_name, Formula=formula_txt, Status="ok", n_rows=nrow(sub), n_subjects=dplyr::n_distinct(sub$SubjectID), stringsAsFactors = FALSE)
  list(status = status, eta = eta_df, anova = anova_out)
}

option_list <- list(
  make_option(c("--long-csv"), type="character"),
  make_option(c("--out-dir"), type="character", default="results/r_analysis2_task2"),
  make_option(c("--group-col"), type="character", default="ExperienceGroup"),
  make_option(c("--exclude-subjects"), type="character", default=""),
  make_option(c("--df-method"), type="character", default="Satterthwaite")
)
opt <- parse_args(OptionParser(option_list=option_list))
if (is.null(opt$`long-csv`)) stop("--long-csv is required")
out_dir <- opt$`out-dir`
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
fig_dir <- file.path(out_dir, "figures")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

use_kr <- tolower(opt$`df-method`) %in% c("kenward-roger", "kenwardroger", "kr")
if (use_kr && !.has_pbkrtest) stop("Kenward-Roger requested but pbkrtest is not installed.")

df <- read_csv(opt$`long-csv`, show_col_types = FALSE)
df <- exclude_subjects(df, opt$`exclude-subjects`)
if (opt$`group-col` == "PeopleGroup4" && !("PeopleGroup4" %in% names(df))) df <- make_people_group4(df)
group_col <- opt$`group-col`
if (!(group_col %in% names(df))) stop(paste("Missing group column:", group_col))

s_specs <- list(
  c("Model1_main", "{dv} ~ WWR + Complexity + {g} + (1 + Complexity | SubjectID)"),
  c("Model2_two_way", "{dv} ~ WWR * Complexity + WWR * {g} + Complexity * {g} + (1 + Complexity | SubjectID)"),
  c("Model3_three_way", "{dv} ~ WWR * Complexity * {g} + (1 + Complexity | SubjectID)")
)
b_specs <- list(
  c("Model1_main_adj", "{dv} ~ WWR + {g} + (1 | SubjectID)"),
  c("Model2_two_way_adj", "{dv} ~ WWR * {g} + (1 | SubjectID)")
)

status_rows <- list(); eta_rows <- list(); anova_rows <- list()

for (dv in intersect(S_DVS, names(df))) {
  for (sp in s_specs) {
    ftxt <- gsub("\\{dv\\}", dv, sp[2])
    ftxt <- gsub("\\{g\\}", group_col, ftxt)
    res <- run_one_model(df, dv, "S", sp[1], ftxt, group_col, use_kr)
    status_rows[[length(status_rows) + 1]] <- res$status
    if (!is.null(res$eta) && nrow(res$eta) > 0) eta_rows[[length(eta_rows) + 1]] <- res$eta
    if (!is.null(res$anova) && nrow(res$anova) > 0) anova_rows[[length(anova_rows) + 1]] <- res$anova
  }
}

b_df <- df
if ("Complexity" %in% names(b_df)) {
  b_df$Complexity <- suppressWarnings(as.numeric(b_df$Complexity))
  b_df <- b_df %>% filter(.data$Complexity == 1)
}
for (dv in intersect(B_DVS, names(b_df))) {
  for (sp in b_specs) {
    ftxt <- gsub("\\{dv\\}", dv, sp[2])
    ftxt <- gsub("\\{g\\}", group_col, ftxt)
    res <- run_one_model(b_df, dv, "B", sp[1], ftxt, group_col, use_kr)
    status_rows[[length(status_rows) + 1]] <- res$status
    if (!is.null(res$eta) && nrow(res$eta) > 0) eta_rows[[length(eta_rows) + 1]] <- res$eta
    if (!is.null(res$anova) && nrow(res$anova) > 0) anova_rows[[length(anova_rows) + 1]] <- res$anova
  }
}

status_df <- bind_rows(status_rows)
eta_df <- bind_rows(eta_rows)
anova_df <- bind_rows(anova_rows)

if (nrow(eta_df) > 0) {
  eta_df <- eta_df %>% arrange(.data$Domain, .data$DV, .data$Model, .data$term)
  eta_sum <- eta_df %>% select(.data$Domain, .data$DV, .data$Model, .data$term, .data$eta2_partial, .data$magnitude, tidyselect::any_of(c("p", "sig")))
  write_csv(eta_df, file.path(out_dir, "analysis2_task2_eta_squared_partial_all.csv"))
  write_csv(eta_sum, file.path(out_dir, "analysis2_task2_eta_squared_partial_summary_all.csv"))

  for (dv in unique(eta_sum$DV)) {
    dd <- eta_sum %>% filter(.data$DV == dv)
    write_csv(dd, file.path(out_dir, paste0("analysis2_task2_eta_squared_partial_", dv, ".csv")))
    plot_eta2_bar(dd, file.path(fig_dir, paste0("analysis2_task2_eta_squared_partial_", dv, ".png")), paste0("Partial η² of fixed effects on ", dv), core_only = FALSE)
    plot_eta2_bar(dd, file.path(fig_dir, paste0("analysis2_task2_eta_squared_partial_", dv, "_core.png")), paste0("Partial η² of core fixed effects on ", dv), core_only = TRUE)
  }
}

if (nrow(anova_df) > 0) write_csv(anova_df, file.path(out_dir, "analysis2_task2_anova_type3_all.csv"))
write_csv(status_df, file.path(out_dir, "analysis2_task2_model_status.csv"))

outs <- c("analysis2_task2_model_status.csv")
if (file.exists(file.path(out_dir, "analysis2_task2_anova_type3_all.csv"))) outs <- c(outs, "analysis2_task2_anova_type3_all.csv")
if (file.exists(file.path(out_dir, "analysis2_task2_eta_squared_partial_all.csv"))) outs <- c(outs, "analysis2_task2_eta_squared_partial_all.csv")
if (file.exists(file.path(out_dir, "analysis2_task2_eta_squared_partial_summary_all.csv"))) outs <- c(outs, "analysis2_task2_eta_squared_partial_summary_all.csv")

cat(toJSON(list(out_dir = out_dir, group_col = group_col, outputs = outs), auto_unbox = TRUE))
