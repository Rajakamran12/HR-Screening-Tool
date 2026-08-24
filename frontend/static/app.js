"use strict";


/* =========================================================
   HR SCREENING TOOL
   FRONTEND APPLICATION
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       DOM REFERENCES
       ===================================================== */

    const fileInput =
        document.querySelector("#fileInput") ||
        document.querySelector("#resumeFile") ||
        document.querySelector('input[type="file"]');

    const uploadZone =
        document.querySelector("#uploadZone") ||
        document.querySelector(".upload-zone");

    const uploadZoneContent =
        document.querySelector(".upload-zone-content");

    const screenButton =
        document.querySelector("#screenButton") ||
        document.querySelector(".screen-button");

    const statusMessage =
        document.querySelector("#statusMessage") ||
        document.querySelector(".status-message");

    const resultsSection =
        document.querySelector("#resultsSection") ||
        document.querySelector(".results-section");


    /* =====================================================
       CONFIGURATION
       ===================================================== */

    const API_ENDPOINTS = {
        screen: "/api/screen"
    };

    const MAX_FILE_SIZE = 10 * 1024 * 1024;

    const ALLOWED_EXTENSIONS = [
        ".pdf",
        ".docx"
    ];

    const ALLOWED_MIME_TYPES = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ];


    /* =====================================================
       STATE
       ===================================================== */

    let selectedFile = null;
    let isScreening = false;


    /* =====================================================
       INITIALIZATION
       ===================================================== */

    initialize();


    function initialize() {

        if (!fileInput) {
            console.error("HR Screening Tool: File input not found.");
        }

        if (!uploadZone) {
            console.error("HR Screening Tool: Upload zone not found.");
        }

        if (!screenButton) {
            console.error("HR Screening Tool: Screen button not found.");
        }

        setupFileInput();
        setupDragAndDrop();
        setupScreeningButton();

        hideResults();

        updateScreenButtonState();
    }


    /* =====================================================
       FILE INPUT
       ===================================================== */

    function setupFileInput() {

        if (!fileInput) {
            return;
        }

        fileInput.addEventListener("change", (event) => {

            const files = event.target.files;

            if (!files || files.length === 0) {
                clearSelectedFile();
                return;
            }

            handleFileSelection(files[0]);
        });
    }


    /* =====================================================
       DRAG & DROP
       ===================================================== */

    function setupDragAndDrop() {

        if (!uploadZone) {
            return;
        }


        uploadZone.addEventListener("dragenter", (event) => {

            event.preventDefault();
            event.stopPropagation();

            uploadZone.classList.add("drag-over");
        });


        uploadZone.addEventListener("dragover", (event) => {

            event.preventDefault();
            event.stopPropagation();

            uploadZone.classList.add("drag-over");

            if (event.dataTransfer) {
                event.dataTransfer.dropEffect = "copy";
            }
        });


        uploadZone.addEventListener("dragleave", (event) => {

            event.preventDefault();
            event.stopPropagation();

            if (!uploadZone.contains(event.relatedTarget)) {
                uploadZone.classList.remove("drag-over");
            }
        });


        uploadZone.addEventListener("drop", (event) => {

            event.preventDefault();
            event.stopPropagation();

            uploadZone.classList.remove("drag-over");

            const files = event.dataTransfer?.files;

            if (!files || files.length === 0) {
                return;
            }

            handleFileSelection(files[0]);
        });


        uploadZone.addEventListener("click", (event) => {

            if (!fileInput) {
                return;
            }

            if (event.target.closest("button")) {
                return;
            }

            fileInput.click();
        });


        uploadZone.addEventListener("keydown", (event) => {

            if (
                event.key === "Enter" ||
                event.key === " "
            ) {

                event.preventDefault();

                if (fileInput) {
                    fileInput.click();
                }
            }
        });
    }


    /* =====================================================
       FILE SELECTION
       ===================================================== */

    function handleFileSelection(file) {

        const validation = validateFile(file);

        if (!validation.valid) {

            selectedFile = null;

            if (fileInput) {
                fileInput.value = "";
            }

            updateUploadUI();

            updateScreenButtonState();

            showStatus(
                validation.message,
                "error"
            );

            return;
        }


        selectedFile = file;

        updateUploadUI();

        updateScreenButtonState();

        showStatus(
            `${file.name} is ready for screening.`,
            "success"
        );
    }


    /* =====================================================
       FILE VALIDATION
       ===================================================== */

    function validateFile(file) {

        if (!file) {

            return {
                valid: false,
                message: "Please select a resume file."
            };
        }


        const fileName =
            String(file.name || "").toLowerCase();

        const extension =
            getFileExtension(fileName);


        if (!ALLOWED_EXTENSIONS.includes(extension)) {

            return {
                valid: false,
                message: "Please upload a PDF or DOCX resume."
            };
        }


        if (file.size <= 0) {

            return {
                valid: false,
                message: "The selected file is empty."
            };
        }


        if (file.size > MAX_FILE_SIZE) {

            return {
                valid: false,
                message: "The file is too large. Maximum size is 10 MB."
            };
        }


        /*
         * Some browsers may not provide the MIME type.
         * Therefore extension validation remains authoritative.
         */
        if (
            file.type &&
            !ALLOWED_MIME_TYPES.includes(file.type) &&
            extension !== ".pdf" &&
            extension !== ".docx"
        ) {

            return {
                valid: false,
                message: "Unsupported resume file type."
            };
        }


        return {
            valid: true,
            message: ""
        };
    }


    function getFileExtension(fileName) {

        const lastDot =
            fileName.lastIndexOf(".");

        if (lastDot === -1) {
            return "";
        }

        return fileName.substring(lastDot);
    }


    /* =====================================================
       UPLOAD UI
       ===================================================== */

    function updateUploadUI() {

        if (!uploadZone) {
            return;
        }


        if (!selectedFile) {

            uploadZone.classList.remove("has-file");

            restoreDefaultUploadContent();

            return;
        }


        uploadZone.classList.add("has-file");

        renderSelectedFile();
    }


    function renderSelectedFile() {

        if (!uploadZoneContent || !selectedFile) {
            return;
        }


        const extension =
            getFileExtension(
                selectedFile.name.toLowerCase()
            );


        const fileSize =
            formatFileSize(selectedFile.size);


        uploadZoneContent.innerHTML = `
            <div class="selected-file">

                <div class="selected-file-icon">
                    ${getFileIcon(extension)}
                </div>

                <div class="selected-file-info">

                    <strong
                        title="${escapeHtml(selectedFile.name)}"
                    >
                        ${escapeHtml(selectedFile.name)}
                    </strong>

                    <span>
                        ${fileSize}
                    </span>

                </div>

                <button
                    type="button"
                    class="remove-file-button"
                    aria-label="Remove selected file"
                >
                    ×
                </button>

            </div>
        `;


        const removeButton =
            uploadZoneContent.querySelector(
                ".remove-file-button"
            );


        if (removeButton) {

            removeButton.addEventListener(
                "click",
                (event) => {

                    event.preventDefault();
                    event.stopPropagation();

                    clearSelectedFile();
                }
            );
        }
    }


    function restoreDefaultUploadContent() {

        if (!uploadZoneContent) {
            return;
        }


        /*
         * Preserve the original HTML supplied by index.html.
         * It is captured lazily the first time this function runs.
         */
        if (!restoreDefaultUploadContent.originalHTML) {

            restoreDefaultUploadContent.originalHTML =
                uploadZoneContent.innerHTML;
        }


        uploadZoneContent.innerHTML =
            restoreDefaultUploadContent.originalHTML;
    }


    function clearSelectedFile() {

        selectedFile = null;

        if (fileInput) {
            fileInput.value = "";
        }

        updateUploadUI();

        updateScreenButtonState();

        clearStatus();
    }


    /* =====================================================
       FILE SIZE
       ===================================================== */

    function formatFileSize(bytes) {

        if (!Number.isFinite(bytes) || bytes <= 0) {
            return "0 KB";
        }


        if (bytes < 1024 * 1024) {

            return `${Math.max(
                1,
                Math.round(bytes / 1024)
            )} KB`;
        }


        return `${(
            bytes / (1024 * 1024)
        ).toFixed(1)} MB`;
    }


    /* =====================================================
       FILE ICON
       ===================================================== */

    function getFileIcon(extension) {

        if (extension === ".pdf") {

            return `
                <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <path d="M14 2v6h6"/>
                    <path d="M8 15h1.5a1.5 1.5 0 0 0 0-3H8v6"/>
                    <path d="M13 18v-6h1.5a2.5 2.5 0 0 1 0 5H13"/>
                    <path d="M19 12h-3v6"/>
                    <path d="M16 15h2.5"/>
                </svg>
            `;
        }


        return `
            <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
            >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <path d="M14 2v6h6"/>
                <path d="M8 13h8"/>
                <path d="M8 17h5"/>
            </svg>
        `;
    }


    /* =====================================================
       SCREENING BUTTON
       ===================================================== */

    function setupScreeningButton() {

        if (!screenButton) {
            return;
        }


        screenButton.addEventListener(
            "click",
            async (event) => {

                event.preventDefault();

                if (isScreening) {
                    return;
                }

                if (!selectedFile) {

                    showStatus(
                        "Please select a resume before screening.",
                        "error"
                    );

                    return;
                }

                await screenCandidate();
            }
        );
    }


    function updateScreenButtonState() {

        if (!screenButton) {
            return;
        }


        screenButton.disabled =
            !selectedFile ||
            isScreening;
    }


    /* =====================================================
       SCREEN CANDIDATE
       ===================================================== */

    async function screenCandidate() {

        if (!selectedFile || isScreening) {
            return;
        }


        isScreening = true;

        updateScreenButtonState();

        setButtonLoading(true);

        showStatus(
            "Analyzing candidate resume...",
            "info"
        );


        try {

            const formData =
                new FormData();

            formData.append(
                "file",
                selectedFile
            );


            const response =
                await fetch(
                    API_ENDPOINTS.screen,
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const data =
                await parseResponse(response);


            if (!response.ok) {

                throw new Error(
                    extractErrorMessage(data) ||
                    `Screening failed with status ${response.status}.`
                );
            }


            const result =
                normalizeScreeningResult(data);


            renderResults(result);


            showStatus(
                "Candidate screening completed successfully.",
                "success"
            );


            scrollToResults();

        } catch (error) {

            console.error(
                "Candidate screening error:",
                error
            );


            showStatus(
                error.message ||
                "Unable to complete candidate screening.",
                "error"
            );

        } finally {

            isScreening = false;

            setButtonLoading(false);

            updateScreenButtonState();
        }
    }


    /* =====================================================
       API RESPONSE
       ===================================================== */

    async function parseResponse(response) {

        const contentType =
            response.headers.get(
                "content-type"
            ) || "";


        if (
            contentType.includes(
                "application/json"
            )
        ) {

            return await response.json();
        }


        const text =
            await response.text();


        try {
            return JSON.parse(text);
        } catch {
            return {
                detail: text
            };
        }
    }


    function extractErrorMessage(data) {

        if (!data) {
            return "";
        }


        if (typeof data === "string") {
            return data;
        }


        if (data.detail) {

            if (typeof data.detail === "string") {
                return data.detail;
            }

            if (Array.isArray(data.detail)) {

                return data.detail
                    .map(item => {

                        if (
                            typeof item === "string"
                        ) {
                            return item;
                        }

                        return (
                            item?.msg ||
                            item?.message ||
                            JSON.stringify(item)
                        );
                    })
                    .join(", ");
            }

            return JSON.stringify(
                data.detail
            );
        }


        return (
            data.message ||
            data.error ||
            ""
        );
    }


    /* =====================================================
       NORMALIZE RESULT
       ===================================================== */

    function normalizeScreeningResult(data) {

        /*
         * The backend schema may return either the scoring
         * object directly or wrap it inside "result".
         */

        const result =
            data?.result ||
            data?.data ||
            data;


        const candidate =
            result?.candidate ||
            {};


        const scores =
            result?.criterion_scores ||
            result?.criteria_scores ||
            result?.scores ||
            result?.criteria ||
            [];


        return {

            candidate: {
                name:
                    candidate.name ||
                    result?.candidate_name ||
                    result?.name ||
                    "Unknown Candidate",

                email:
                    candidate.email ||
                    result?.candidate_email ||
                    result?.email ||
                    "Not available",

                phone:
                    candidate.phone ||
                    result?.candidate_phone ||
                    result?.phone ||
                    "Not available",

                experience:
                    candidate.experience ||
                    result?.experience ||
                    result?.years_of_experience ||
                    "Not available"
            },


            overallScore:
                result?.overall_score ??
                result?.overallScore ??
                result?.score ??
                0,


            recommendation:
                result?.recommendation ||
                result?.decision ||
                result?.status ||
                "Review",


            summary:
                result?.summary ||
                result?.candidate_summary ||
                result?.overall_summary ||
                "No summary available.",


            strengths:
                normalizeList(
                    result?.strengths
                ),


            gaps:
                normalizeList(
                    result?.gaps ||
                    result?.weaknesses ||
                    result?.areas_for_improvement
                ),


            criteria:
                normalizeCriteria(scores)
        };
    }


    function normalizeList(value) {

        if (!value) {
            return [];
        }


        if (Array.isArray(value)) {

            return value
                .map(item => {

                    if (
                        typeof item === "string"
                    ) {
                        return item;
                    }

                    if (
                        item &&
                        typeof item === "object"
                    ) {

                        return (
                            item.text ||
                            item.description ||
                            item.reason ||
                            item.name ||
                            JSON.stringify(item)
                        );
                    }

                    return String(item);
                })
                .filter(Boolean);
        }


        if (typeof value === "string") {

            return value
                .split(/\r?\n/)
                .map(item =>
                    item
                        .replace(/^[-•*]\s*/, "")
                        .trim()
                )
                .filter(Boolean);
        }


        return [];
    }


    function normalizeCriteria(criteria) {

        if (!criteria) {
            return [];
        }


        if (Array.isArray(criteria)) {

            return criteria.map(
                normalizeCriterion
            );
        }


        if (
            typeof criteria === "object"
        ) {

            return Object.entries(criteria)
                .map(([name, value]) => {

                    if (
                        value &&
                        typeof value === "object" &&
                        !Array.isArray(value)
                    ) {

                        return normalizeCriterion({
                            name,
                            ...value
                        });
                    }


                    return normalizeCriterion({
                        name,
                        score: value
                    });
                });
        }


        return [];
    }


    function normalizeCriterion(item) {

        if (
            !item ||
            typeof item !== "object"
        ) {

            return {
                name: "Criterion",
                score: 0,
                evidence: "",
                reasoning: "",
                requirement: ""
            };
        }


        const score =
            Number(
                item.score ??
                item.rating ??
                item.value ??
                item.points ??
                0
            );


        return {

            name:
                item.name ||
                item.criterion ||
                item.title ||
                "Criterion",


            score:
                Number.isFinite(score)
                    ? score
                    : 0,


            evidence:
                item.evidence ||
                item.matched_evidence ||
                item.candidate_evidence ||
                "",


            reasoning:
                item.reasoning ||
                item.explanation ||
                item.justification ||
                "",


            requirement:
                item.requirement ||
                item.expected ||
                item.criteria ||
                ""
        };
    }


    /* =====================================================
       RESULT RENDERING
       ===================================================== */

    function renderResults(result) {

        if (!resultsSection) {
            return;
        }


        renderCandidateOverview(
            result
        );


        renderRecommendation(
            result.recommendation
        );


        renderSummary(
            result.summary
        );


        renderList(
            ".strengths-card .result-list",
            result.strengths,
            "No significant strengths identified."
        );


        renderList(
            ".gaps-card .result-list",
            result.gaps,
            "No significant gaps identified."
        );


        renderCriteria(
            result.criteria
        );


        resultsSection.hidden = false;

        resultsSection.style.display = "";
    }


    /* =====================================================
       CANDIDATE OVERVIEW
       ===================================================== */

    function renderCandidateOverview(result) {

        const candidate =
            result.candidate;


        const candidateName =
            document.querySelector(
                "#candidateName"
            ) ||
            document.querySelector(
                ".candidate-identity h3"
            );


        const candidateEmail =
            document.querySelector(
                "#candidateEmail"
            );


        const candidatePhone =
            document.querySelector(
                "#candidatePhone"
            );


        const candidateExperience =
            document.querySelector(
                "#candidateExperience"
            );


        const overallScore =
            document.querySelector(
                "#overallScore"
            ) ||
            document.querySelector(
                ".score-metric strong"
            );


        if (candidateName) {

            candidateName.textContent =
                candidate.name;
        }


        if (candidateEmail) {

            candidateEmail.textContent =
                candidate.email;
        }


        if (candidatePhone) {

            candidatePhone.textContent =
                candidate.phone;
        }


        if (candidateExperience) {

            candidateExperience.textContent =
                candidate.experience;
        }


        if (overallScore) {

            overallScore.textContent =
                formatScore(
                    result.overallScore
                );
        }


        /*
         * Support the existing metric layout even if
         * the HTML uses data attributes instead of IDs.
         */

        const overviewMetrics =
            document.querySelectorAll(
                ".overview-metric"
            );


        overviewMetrics.forEach(
            metric => {

                const label =
                    metric.querySelector(
                        ".field-label"
                    )?.textContent
                    ?.trim()
                    ?.toLowerCase();


                const value =
                    metric.querySelector(
                        "strong"
                    );


                if (!value) {
                    return;
                }


                if (
                    label?.includes("email") &&
                    !candidateEmail
                ) {

                    value.textContent =
                        candidate.email;
                }


                if (
                    label?.includes("phone") &&
                    !candidatePhone
                ) {

                    value.textContent =
                        candidate.phone;
                }


                if (
                    (
                        label?.includes("experience") ||
                        label?.includes("exp")
                    ) &&
                    !candidateExperience
                ) {

                    value.textContent =
                        candidate.experience;
                }


                if (
                    label?.includes("score") &&
                    !overallScore
                ) {

                    value.textContent =
                        formatScore(
                            result.overallScore
                        );
                }
            }
        );
    }


    /* =====================================================
       SCORE FORMATTING
       ===================================================== */

    function formatScore(score) {

        const numericScore =
            Number(score);


        if (!Number.isFinite(numericScore)) {
            return "0";
        }


        const normalized =
            numericScore <= 1
                ? numericScore * 100
                : numericScore;


        return `${Math.round(
            Math.max(
                0,
                Math.min(
                    100,
                    normalized
                )
            )
        )}%`;
    }


    function scoreToPercentage(score) {

        const numericScore =
            Number(score);


        if (!Number.isFinite(numericScore)) {
            return 0;
        }


        /*
         * Criterion scores may be:
         *
         * 0-1
         * 0-5
         * 0-10
         * 0-100
         */

        if (numericScore <= 1) {
            return numericScore * 100;
        }


        if (numericScore <= 5) {
            return numericScore * 20;
        }


        if (numericScore <= 10) {
            return numericScore * 10;
        }


        return Math.max(
            0,
            Math.min(
                100,
                numericScore
            )
        );
    }


    /* =====================================================
       RECOMMENDATION
       ===================================================== */

    function renderRecommendation(
        recommendation
    ) {

        const badge =
            document.querySelector(
                "#resultBadge"
            ) ||
            document.querySelector(
                ".result-badge"
            );


        if (!badge) {
            return;
        }


        const normalized =
            String(
                recommendation ||
                "Review"
            )
                .trim();


        const lower =
            normalized.toLowerCase();


        badge.classList.remove(
            "review",
            "error"
        );


        if (
            lower.includes("reject") ||
            lower.includes("not qualified") ||
            lower.includes("disqual")
        ) {

            badge.classList.add(
                "error"
            );

        } else if (
            lower.includes("review") ||
            lower.includes("consider") ||
            lower.includes("maybe")
        ) {

            badge.classList.add(
                "review"
            );
        }


        badge.textContent =
            normalized;
    }


    /* =====================================================
       SUMMARY
       ===================================================== */

    function renderSummary(summary) {

        const summaryElement =
            document.querySelector(
                "#summaryText"
            ) ||
            document.querySelector(
                ".summary-text"
            );


        if (!summaryElement) {
            return;
        }


        summaryElement.textContent =
            summary ||
            "No summary available.";
    }


    /* =====================================================
       STRENGTHS / GAPS
       ===================================================== */

    function renderList(
        selector,
        items,
        emptyMessage
    ) {

        const list =
            document.querySelector(
                selector
            );


        if (!list) {
            return;
        }


        list.innerHTML = "";


        if (
            !items ||
            items.length === 0
        ) {

            const li =
                document.createElement("li");

            li.textContent =
                emptyMessage;

            list.appendChild(li);

            return;
        }


        items.forEach(item => {

            const li =
                document.createElement("li");

            li.textContent =
                item;

            list.appendChild(li);
        });
    }


    /* =====================================================
       CRITERION SCORES
       ===================================================== */

    function renderCriteria(criteria) {

        const container =
            document.querySelector(
                "#criterionScores"
            ) ||
            document.querySelector(
                ".criterion-scores"
            );


        if (!container) {
            return;
        }


        container.innerHTML = "";


        if (
            !criteria ||
            criteria.length === 0
        ) {

            const empty =
                document.createElement("div");

            empty.className =
                "criterion-empty";

            empty.textContent =
                "No criterion-level scores available.";

            container.appendChild(empty);

            return;
        }


        criteria.forEach(
            criterion => {

                container.appendChild(
                    createCriterionElement(
                        criterion
                    )
                );
            }
        );
    }


    function createCriterionElement(
        criterion
    ) {

        const item =
            document.createElement("div");

        item.className =
            "criterion-item";


        const percentage =
            scoreToPercentage(
                criterion.score
            );


        const scoreText =
            formatCriterionScore(
                criterion.score
            );


        item.innerHTML = `
            <div class="criterion-top">

                <div class="criterion-name">
                    ${escapeHtml(
                        criterion.name
                    )}
                </div>

                <div class="criterion-score">
                    ${escapeHtml(
                        scoreText
                    )}
                </div>

            </div>


            <div class="criterion-progress">

                <div
                    class="criterion-progress-bar"
                    style="width: ${percentage}%"
                ></div>

            </div>


            <div class="criterion-details">

                <div class="criterion-detail">

                    <span class="criterion-detail-label">
                        Requirement
                    </span>

                    <div class="criterion-detail-value">
                        ${escapeHtml(
                            criterion.requirement ||
                            "Not provided"
                        )}
                    </div>

                </div>


                <div class="criterion-detail">

                    <span class="criterion-detail-label">
                        Evidence
                    </span>

                    <div class="criterion-detail-value">
                        ${escapeHtml(
                            criterion.evidence ||
                            "No evidence provided"
                        )}
                    </div>

                </div>


                <div class="criterion-detail">

                    <span class="criterion-detail-label">
                        Reasoning
                    </span>

                    <div class="criterion-detail-value">
                        ${escapeHtml(
                            criterion.reasoning ||
                            "No reasoning provided"
                        )}
                    </div>

                </div>

            </div>
        `;


        return item;
    }


    function formatCriterionScore(score) {

        const numericScore =
            Number(score);


        if (!Number.isFinite(numericScore)) {
            return "0";
        }


        if (numericScore <= 1) {

            return `${Math.round(
                numericScore * 100
            )}%`;
        }


        if (numericScore <= 5) {

            return `${numericScore}/5`;
        }


        if (numericScore <= 10) {

            return `${numericScore}/10`;
        }


        return `${Math.round(
            numericScore
        )}%`;
    }


    /* =====================================================
       BUTTON LOADING
       ===================================================== */

    function setButtonLoading(
        loading
    ) {

        if (!screenButton) {
            return;
        }


        if (loading) {

            screenButton.classList.add(
                "loading"
            );

            screenButton.setAttribute(
                "aria-busy",
                "true"
            );

        } else {

            screenButton.classList.remove(
                "loading"
            );

            screenButton.removeAttribute(
                "aria-busy"
            );
        }
    }


    /* =====================================================
       STATUS MESSAGE
       ===================================================== */

    function showStatus(
        message,
        type = "info"
    ) {

        if (!statusMessage) {
            return;
        }


        statusMessage.textContent =
            message;


        statusMessage.dataset.type =
            type;


        statusMessage.hidden = false;

        statusMessage.style.display =
            "flex";
    }


    function clearStatus() {

        if (!statusMessage) {
            return;
        }


        statusMessage.textContent = "";

        delete statusMessage.dataset.type;

        statusMessage.hidden = true;

        statusMessage.style.display =
            "none";
    }


    /* =====================================================
       RESULTS VISIBILITY
       ===================================================== */

    function hideResults() {

        if (!resultsSection) {
            return;
        }


        resultsSection.hidden = true;

        resultsSection.style.display =
            "none";
    }


    function scrollToResults() {

        if (!resultsSection) {
            return;
        }


        window.setTimeout(() => {

            resultsSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        }, 100);
    }


    /* =====================================================
       HTML ESCAPING
       ===================================================== */

    function escapeHtml(value) {

        if (
            value === null ||
            value === undefined
        ) {
            return "";
        }


        return String(value)
            .replace(
                /&/g,
                "&amp;"
            )
            .replace(
                /</g,
                "&lt;"
            )
            .replace(
                />/g,
                "&gt;"
            )
            .replace(
                /"/g,
                "&quot;"
            )
            .replace(
                /'/g,
                "&#039;"
            );
    }

});