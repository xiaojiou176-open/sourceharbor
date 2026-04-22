"use client";

import {
	type ComponentProps,
	type ReactNode,
	useId,
	useMemo,
	useRef,
	useState,
} from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const EMPTY_SELECT_VALUE = "__EMPTY_OPTION__";

type FormFieldProps = ComponentProps<"div">;
type FormFieldLabelProps = ComponentProps<typeof Label>;
type FormFieldHintProps = ComponentProps<"p">;
type FormFieldErrorProps = ComponentProps<"p">;

type FormSelectOption = {
	value: string;
	label: ReactNode;
	disabled?: boolean;
};

type FormInputFieldProps = {
	label: ReactNode;
	hint?: ReactNode;
	error?: ReactNode;
	fieldClassName?: string;
	inputClassName?: string;
	labelClassName?: string;
	hintClassName?: string;
	errorClassName?: string;
} & ComponentProps<typeof Input>;

type FormSelectFieldProps = {
	label: ReactNode;
	hint?: ReactNode;
	error?: ReactNode;
	options: FormSelectOption[];
	fieldClassName?: string;
	selectClassName?: string;
	labelClassName?: string;
	hintClassName?: string;
	errorClassName?: string;
} & Omit<ComponentProps<"select">, "children">;

type FormCheckboxFieldProps = {
	label: ReactNode;
	hint?: ReactNode;
	error?: ReactNode;
	fieldClassName?: string;
	checkboxClassName?: string;
	labelClassName?: string;
	hintClassName?: string;
	errorClassName?: string;
} & Omit<ComponentProps<"input">, "type">;

function toFieldId(name: string | undefined, fallbackId: string): string {
	const normalizedFallback = fallbackId.replace(/[^a-zA-Z0-9_-]/g, "-");
	if (!name) {
		return `field-${normalizedFallback}`;
	}
	return `field-${name.replace(/[^a-zA-Z0-9_-]/g, "-")}-${normalizedFallback}`;
}

function resolveDescribedBy(
	...ids: Array<string | undefined>
): string | undefined {
	const normalized = ids.filter((value): value is string => Boolean(value));
	return normalized.length > 0 ? normalized.join(" ") : undefined;
}

export function FormField({ className, ...props }: FormFieldProps) {
	return (
		<div
			data-slot="form-field"
			className={cn("grid gap-2", className)}
			{...props}
		/>
	);
}

export function FormFieldLabel({ className, ...props }: FormFieldLabelProps) {
	return <Label className={cn("text-sm font-medium", className)} {...props} />;
}

export function FormFieldHint({ className, ...props }: FormFieldHintProps) {
	return (
		<p className={cn("text-sm text-muted-foreground", className)} {...props} />
	);
}

export function FormFieldError({ className, ...props }: FormFieldErrorProps) {
	return (
		<p
			role="alert"
			className={cn("text-sm text-destructive", className)}
			{...props}
		/>
	);
}

export function FormInputField({
	label,
	hint,
	error,
	fieldClassName,
	inputClassName,
	labelClassName,
	hintClassName,
	errorClassName,
	name,
	id,
	"aria-describedby": ariaDescribedBy,
	...props
}: FormInputFieldProps) {
	const autoId = useId();
	const fieldId = id ?? toFieldId(name, autoId);
	const hintId = hint ? `${fieldId}-hint` : undefined;
	const errorId = error ? `${fieldId}-error` : undefined;
	const describedBy = resolveDescribedBy(ariaDescribedBy, hintId, errorId);

	return (
		<FormField className={fieldClassName}>
			<FormFieldLabel htmlFor={fieldId} className={labelClassName}>
				{label}
			</FormFieldLabel>
			<Input
				{...props}
				id={fieldId}
				name={name}
				className={cn("w-full", inputClassName)}
				aria-describedby={describedBy}
				aria-invalid={Boolean(error) || props["aria-invalid"]}
			/>
			{hint ? (
				<FormFieldHint id={hintId} className={hintClassName}>
					{hint}
				</FormFieldHint>
			) : null}
			{error ? (
				<FormFieldError id={errorId} className={errorClassName}>
					{error}
				</FormFieldError>
			) : null}
		</FormField>
	);
}

export function FormSelectField({
	label,
	hint,
	error,
	options,
	fieldClassName,
	selectClassName,
	labelClassName,
	hintClassName,
	errorClassName,
	name,
	id,
	"aria-describedby": ariaDescribedBy,
	...props
}: FormSelectFieldProps) {
	const autoId = useId();
	const fieldId = id ?? toFieldId(name, autoId);
	const hintId = hint ? `${fieldId}-hint` : undefined;
	const errorId = error ? `${fieldId}-error` : undefined;
	const describedBy = resolveDescribedBy(ariaDescribedBy, hintId, errorId);
	const controlledValue =
		typeof props.value === "string" ? props.value : undefined;
	const initialValue = useMemo(() => {
		if (controlledValue !== undefined) {
			return controlledValue;
		}
		if (typeof props.defaultValue === "string") {
			return props.defaultValue;
		}
		return options[0]?.value ?? "";
	}, [controlledValue, options, props.defaultValue]);
	const [uncontrolledValue, setUncontrolledValue] = useState(initialValue);
	const value = controlledValue ?? uncontrolledValue;
	const selectValue = value === "" ? EMPTY_SELECT_VALUE : value;
	const placeholder =
		typeof label === "string" ? `Select ${label}` : "Select an option";

	return (
		<FormField className={fieldClassName}>
			<FormFieldLabel htmlFor={fieldId} className={labelClassName}>
				{label}
			</FormFieldLabel>
			<input id={`${fieldId}-value`} type="hidden" name={name} value={value} />
			<Select
				name={name}
				value={selectValue}
				onValueChange={(nextValue) => {
					setUncontrolledValue(
						nextValue === EMPTY_SELECT_VALUE ? "" : nextValue,
					);
				}}
				disabled={props.disabled}
			>
				<SelectTrigger
					id={fieldId}
					aria-label={typeof label === "string" ? label : undefined}
					aria-describedby={describedBy}
					aria-invalid={Boolean(error) || props["aria-invalid"]}
					className={cn("w-full", selectClassName)}
				>
					<SelectValue placeholder={placeholder} />
				</SelectTrigger>
				<SelectContent>
					{options.map((option) => (
						<SelectItem
							key={option.value || EMPTY_SELECT_VALUE}
							value={option.value === "" ? EMPTY_SELECT_VALUE : option.value}
							disabled={option.disabled}
						>
							{option.label}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
			{hint ? (
				<FormFieldHint id={hintId} className={hintClassName}>
					{hint}
				</FormFieldHint>
			) : null}
			{error ? (
				<FormFieldError id={errorId} className={errorClassName}>
					{error}
				</FormFieldError>
			) : null}
		</FormField>
	);
}

export function FormCheckboxField({
	label,
	hint,
	error,
	fieldClassName,
	checkboxClassName,
	labelClassName,
	hintClassName,
	errorClassName,
	name,
	id,
	"aria-describedby": ariaDescribedBy,
	...props
}: FormCheckboxFieldProps) {
	const autoId = useId();
	const fieldId = id ?? toFieldId(name, autoId);
	const hintId = hint ? `${fieldId}-hint` : undefined;
	const errorId = error ? `${fieldId}-error` : undefined;
	const describedBy = resolveDescribedBy(ariaDescribedBy, hintId, errorId);
	const isControlled = typeof props.checked === "boolean";
	const [uncontrolledChecked, setUncontrolledChecked] = useState(
		Boolean(props.defaultChecked),
	);
	const checked = isControlled ? Boolean(props.checked) : uncontrolledChecked;
	const hiddenInputRef = useRef<HTMLInputElement | null>(null);

	return (
		<FormField className={cn("gap-2.5", fieldClassName)}>
			<div className="flex items-center gap-3">
				<input
					ref={hiddenInputRef}
					type="hidden"
					name={name}
					value={checked ? "on" : ""}
				/>
				<Checkbox
					id={fieldId}
					className={checkboxClassName}
					checked={checked}
					disabled={props.disabled}
					aria-describedby={describedBy}
					aria-invalid={Boolean(error) || props["aria-invalid"]}
					onCheckedChange={(nextChecked) => {
						const resolvedChecked = nextChecked === true;
						if (!isControlled) {
							setUncontrolledChecked(resolvedChecked);
							if (hiddenInputRef.current) {
								hiddenInputRef.current.value = resolvedChecked ? "on" : "";
								hiddenInputRef.current.dispatchEvent(
									new Event("input", { bubbles: true }),
								);
								hiddenInputRef.current.dispatchEvent(
									new Event("change", { bubbles: true }),
								);
							}
						}
						props.onChange?.({
							target: {
								checked: resolvedChecked,
								id: fieldId,
								name,
								value: resolvedChecked ? "on" : "",
							},
						} as unknown as React.ChangeEvent<HTMLInputElement>);
					}}
				/>
				<FormFieldLabel
					htmlFor={fieldId}
					className={cn("cursor-pointer", labelClassName)}
				>
					{label}
				</FormFieldLabel>
			</div>
			{hint ? (
				<FormFieldHint id={hintId} className={cn("pl-7", hintClassName)}>
					{hint}
				</FormFieldHint>
			) : null}
			{error ? (
				<FormFieldError id={errorId} className={cn("pl-7", errorClassName)}>
					{error}
				</FormFieldError>
			) : null}
		</FormField>
	);
}
