"use client";

import { resolveWriteSessionToken } from "@/lib/api/url";

type Props = {
	sessionToken?: string | null;
};

export function WebActionSessionHiddenInput({ sessionToken }: Props) {
	return (
		<input
			type="hidden"
			name="session_token"
			value={resolveWriteSessionToken(sessionToken) ?? ""}
			suppressHydrationWarning
		/>
	);
}
