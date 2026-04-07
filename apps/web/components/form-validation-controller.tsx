"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { getLocaleMessages } from "@/lib/i18n/messages";

const FORM_VALIDATION_MESSAGE_NODE_ATTR = "data-form-validation-message";
const SUBMIT_REASON_BASE_DESCRIBED_BY = "data-submit-base-describedby";
const FORM_VALIDATION_HINT_BASE_CLASS = "form-validation-hint";
const FORM_VALIDATION_HINT_ACTIVE_CLASS = "form-validation-hint-active";

let formValidationMessageCounter = 0;

function isBlank(value: string | null | undefined): boolean {
	return !value || value.trim().length === 0;
}

function getOrCreateValidationMessageNode(
	form: HTMLFormElement,
): HTMLOutputElement {
	const existing = form.querySelector<HTMLOutputElement>(
		`output[${FORM_VALIDATION_MESSAGE_NODE_ATTR}="true"]`,
	);
	if (existing) {
		return existing;
	}

	const output = document.createElement("output");
	formValidationMessageCounter += 1;
	output.id = `form-validation-message-${formValidationMessageCounter}`;
	output.setAttribute(FORM_VALIDATION_MESSAGE_NODE_ATTR, "true");
	output.setAttribute("aria-live", "polite");
	output.setAttribute("aria-atomic", "true");
	output.setAttribute("role", "status");
	output.className = FORM_VALIDATION_HINT_BASE_CLASS;
	output.setAttribute("data-state", "idle");
	output.hidden = true;
	form.append(output);
	return output;
}

function updateSubmitReasonA11y(
	submit: HTMLButtonElement | HTMLInputElement,
	reasonNode: HTMLOutputElement,
	reason: string | null,
): void {
	if (!submit.hasAttribute(SUBMIT_REASON_BASE_DESCRIBED_BY)) {
		submit.setAttribute(
			SUBMIT_REASON_BASE_DESCRIBED_BY,
			submit.getAttribute("aria-describedby") ?? "",
		);
	}
	const baseDescribedBy = (
		submit.getAttribute(SUBMIT_REASON_BASE_DESCRIBED_BY) ?? ""
	)
		.split(/\s+/)
		.filter((token) => token.length > 0 && token !== reasonNode.id);

	if (!reason) {
		reasonNode.setAttribute("aria-live", "polite");
		reasonNode.setAttribute("role", "status");
		reasonNode.setAttribute("data-state", "idle");
		reasonNode.className = FORM_VALIDATION_HINT_BASE_CLASS;
		reasonNode.textContent = "";
		reasonNode.hidden = true;
		submit.removeAttribute("title");
		if (baseDescribedBy.length > 0) {
			submit.setAttribute("aria-describedby", baseDescribedBy.join(" "));
		} else {
			submit.removeAttribute("aria-describedby");
		}
		return;
	}

	reasonNode.setAttribute("aria-live", "assertive");
	reasonNode.setAttribute("role", "alert");
	reasonNode.setAttribute("data-state", "active");
	reasonNode.className = `${FORM_VALIDATION_HINT_BASE_CLASS} ${FORM_VALIDATION_HINT_ACTIVE_CLASS}`;
	reasonNode.hidden = false;
	reasonNode.textContent = reason;
	submit.setAttribute("title", reason);
	submit.setAttribute(
		"aria-describedby",
		[...baseDescribedBy, reasonNode.id].join(" "),
	);
}

function evaluateForm(form: HTMLFormElement): void {
	const disableReasonMessages = getLocaleMessages().formValidation;
	const submit = form.querySelector<HTMLButtonElement | HTMLInputElement>(
		'button[type="submit"], input[type="submit"]',
	);
	if (!submit) {
		return;
	}

	let hasRequiredViolation = false;
	if (form.dataset.autoDisableRequired === "true") {
		const requiredFields = Array.from(
			form.querySelectorAll<
				HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
			>("[required]"),
		);
		hasRequiredViolation = requiredFields.some(
			(field) =>
				isBlank((field as HTMLInputElement).value) || !field.checkValidity(),
		);
	}

	let hasRequireOneViolation = false;
	let hasRequireOneExclusiveViolation = false;
	const requireOne = form.dataset.requireOne;
	const requireOneExclusive = form.dataset.requireOneExclusive === "true";
	if (requireOne) {
		const names = requireOne
			.split(",")
			.map((item) => item.trim())
			.filter((item) => item.length > 0);
		if (names.length > 0) {
			const filledCount = names.filter((name) => {
				const field = form.querySelector<
					HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
				>(`[name="${name}"]`);
				return !isBlank(field?.value);
			}).length;
			hasRequireOneViolation = filledCount < 1;
			if (requireOneExclusive && filledCount > 1) {
				hasRequireOneExclusiveViolation = true;
			}
		}
	}

	const disabled =
		hasRequiredViolation ||
		hasRequireOneViolation ||
		hasRequireOneExclusiveViolation;
	let disableReason: string | null = null;
	if (hasRequireOneExclusiveViolation) {
		disableReason = disableReasonMessages.requireOneExclusive;
	} else if (hasRequireOneViolation) {
		disableReason = disableReasonMessages.requireOne;
	} else if (hasRequiredViolation) {
		disableReason = disableReasonMessages.required;
	}

	submit.disabled = disabled;
	submit.setAttribute("aria-disabled", disabled ? "true" : "false");
	const reasonNode = getOrCreateValidationMessageNode(form);
	updateSubmitReasonA11y(submit, reasonNode, disableReason);

	const dependentFields = Array.from(
		form.querySelectorAll<
			HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
		>("[data-disabled-unless-checked]"),
	);
	dependentFields.forEach((field) => {
		const controllerName = field.getAttribute("data-disabled-unless-checked");
		if (!controllerName) {
			return;
		}
		const checkboxController = form.querySelector<HTMLInputElement>(
			`input[type="checkbox"][name="${controllerName}"]`,
		);
		const hiddenController = form.querySelector<HTMLInputElement>(
			`input[type="hidden"][name="${controllerName}"]`,
		);
		const enabled = checkboxController
			? Boolean(checkboxController.checked)
			: Boolean(hiddenController?.value);
		field.disabled = !enabled;
		field.setAttribute("aria-disabled", enabled ? "false" : "true");
	});
}

function evaluateAllForms(): void {
	const forms = new Set<HTMLFormElement>();
	document
		.querySelectorAll<Element>(
			"form[data-auto-disable-required], form[data-require-one], form [data-disabled-unless-checked]",
		)
		.forEach((node) => {
			if (node instanceof HTMLFormElement) {
				forms.add(node);
				return;
			}
			const parentForm = node.closest("form");
			if (parentForm instanceof HTMLFormElement) {
				forms.add(parentForm);
			}
		});
	forms.forEach((form) => {
		evaluateForm(form);
	});
}

export function FormValidationController(): null {
	const pathname = usePathname();

	useEffect(() => {
		void pathname;
		const onInput = (event: Event) => {
			const target = event.target;
			if (!(target instanceof Element)) {
				return;
			}
			const form = target.closest("form");
			if (form instanceof HTMLFormElement) {
				evaluateForm(form);
			}
		};

		evaluateAllForms();
		document.addEventListener("input", onInput, true);
		document.addEventListener("change", onInput, true);

		return () => {
			document.removeEventListener("input", onInput, true);
			document.removeEventListener("change", onInput, true);
		};
	}, [pathname]);

	return null;
}
