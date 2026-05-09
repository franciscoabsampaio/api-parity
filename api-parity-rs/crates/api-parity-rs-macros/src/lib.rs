//! Attribute macros for api-parity-rs (port-side plugin).
//!
//! Domain-agnostic: the `path` value can name a PySpark API, a REST
//! endpoint, a TypeScript type — anything `api-parity` can left-join on.
//!
//! Two forms:
//!
//! - `#[parity_impl(...)]` on an `impl` block. Its `path` (if any) acts as
//!   a *prefix* for relative child paths; if `path` AND `status` are both
//!   present, an entry is also registered for the impl itself, with the
//!   implementation set to the type name (e.g. `SparkSession`).
//! - `#[parity(...)]` on a method or free `fn`. Inside an `#[parity_impl]`,
//!   a leading `.` in `path` (e.g. `.builder`) is replaced at compile time
//!   with `parent_path + child` (e.g. `pyspark.sql.session.SparkSession.builder`).
//!
//! Recognized arguments:
//! - `path = "..."` (required to emit an entry).
//! - `status = Implemented | Partial | Unimplemented` (required to emit an entry).
//! - `since = "..."`, `comment = "..."`, `issue = 42` (optional).
//! - `status = Unimplemented` requires a `comment` — the whole point of a
//!   stub is that the comment explains *why* it's unimplemented.

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TS2;
use quote::quote;
use syn::{
    parse_macro_input, spanned::Spanned, Attribute, Error, ImplItem, ItemFn,
    ItemImpl, LitInt, LitStr,
};

/// Parsed `#[parity(...)]` arguments. Used by both macros.
#[derive(Default)]
struct ParityArgs {
    path: Option<LitStr>,
    status: Option<syn::Ident>,
    since: Option<LitStr>,
    comment: Option<LitStr>,
    issue: Option<LitInt>,
}

fn parse_args(attr: &Attribute) -> Result<ParityArgs, Error> {
    let mut args = ParityArgs::default();
    // `parse_nested_meta` walks `key = value` pairs and calls the closure
    // once per pair. Returning `Err` propagates as a `syn::Error` with
    // the right span pointing at the offending token.
    attr.parse_nested_meta(|meta| {
        if meta.path.is_ident("path") {
            args.path = Some(meta.value()?.parse()?);
        } else if meta.path.is_ident("status") {
            args.status = Some(meta.value()?.parse()?);
        } else if meta.path.is_ident("since") {
            args.since = Some(meta.value()?.parse()?);
        } else if meta.path.is_ident("comment") {
            args.comment = Some(meta.value()?.parse()?);
        } else if meta.path.is_ident("issue") {
            args.issue = Some(meta.value()?.parse()?);
        } else {
            // Unknown key: reject loudly so typos don't silently no-op.
            return Err(meta.error(format!(
                "parity: unknown argument `{}` (expected one of: path, status, since, comment, issue)",
                meta.path.get_ident().map(|i| i.to_string()).unwrap_or_default(),
            )));
        }
        Ok(())
    })?;
    Ok(args)
}

/// Attribute on an `impl` block. Walks the block's methods, strips any
/// `#[parity(...)]` attributes, and emits one `inventory::submit!` per
/// stripped attribute. The implementation path is `Self::fn_name`, so
/// the type prefix is auto-derived (the user doesn't have to repeat it).
///
/// Output token stream layout:
/// ```text
/// <original impl block, with #[parity] attrs removed from methods>
/// <one inventory::submit! { ParityEntry { ... } } per stripped attr>
/// ```
/// The submits sit at module scope next to the impl, which is where
/// `inventory::submit!` expects them.
#[proc_macro_attribute]
pub fn parity_impl(args: TokenStream, input: TokenStream) -> TokenStream {
    // Parse the annotated item as an `impl` block. `parse_macro_input!`
    // bails with a compile error if the input isn't an impl.
    let mut item: ItemImpl = parse_macro_input!(input as ItemImpl);

    // `self_ty` is the type after `impl`, e.g. `SparkSession` or
    // `Foo<'a, T>`. Stringify it (stripping the spaces the token-printer
    // adds) to use as the impl path of every annotated method.
    let self_ty = &item.self_ty;
    let self_ty_str = quote!(#self_ty).to_string().replace(' ', "");

    // Parse the impl-level args once. Wrap in a fake attribute so we can
    // reuse `parse_args` (which expects a `syn::Attribute`).
    let args2: TS2 = args.into();
    let parent_attr: Attribute = syn::parse_quote!(#[parity(#args2)]);
    let parent_args = match parse_args(&parent_attr) {
        Ok(a) => a,
        Err(e) => return e.into_compile_error().into(),
    };
    let parent_path_str = parent_args.path.as_ref().map(|r| r.value());

    // Accumulator for all submit! calls we emit alongside the impl.
    let mut submits = TS2::new();

    // If the impl declares both path and status, register the class
    // itself. The implementation here is the type name (e.g. `SparkSession`),
    // mirroring how methods get a `Self::fn_name` impl path.
    if parent_args.path.is_some() && parent_args.status.is_some() {
        let lit = LitStr::new(&self_ty_str, proc_macro2::Span::call_site());
        let tokens = build_submit(&parent_args, parent_attr.span(), quote!(#lit), None)
            .unwrap_or_else(Error::into_compile_error);
        submits.extend(tokens);
    }

    for impl_item in &mut item.items {
        // Only methods are interesting; skip consts, types, etc.
        if let ImplItem::Fn(method) = impl_item {
            // Take all `#[parity(...)]` attrs off the method (so they
            // don't reach rustc as unknown attrs) and remember them.
            // `Vec::retain` lets us partition in place.
            let mut child_attrs = Vec::new();
            method.attrs.retain(|attr| {
                if attr.path().is_ident("parity") {
                    child_attrs.push(attr.clone());
                    false // drop from the method
                } else {
                    true // keep other attrs (e.g. #[inline])
                }
            });

            // For each removed `#[parity(...)]` build a submit! call.
            // Multiple per method is allowed but unusual.
            for attr in child_attrs {
                let fn_name = method.sig.ident.to_string();
                let impl_path = format!("{}::{}", self_ty_str, fn_name);
                let lit = LitStr::new(&impl_path, proc_macro2::Span::call_site());
                let tokens = match parse_args(&attr) {
                    Ok(child) => build_submit(
                        &child,
                        attr.span(),
                        quote!(#lit),
                        parent_path_str.as_deref(),
                    )
                    .unwrap_or_else(Error::into_compile_error),
                    Err(e) => e.into_compile_error(),
                };
                submits.extend(tokens);
            }
        }
    }

    // Emit the (now de-attributed) impl followed by the submits.
    let out = quote! {
        #item
        #submits
    };
    out.into()
}

/// Attribute on a free `fn`. Used when there's no enclosing impl block to
/// provide a type prefix; the implementation path becomes
/// `module_path!()::fn_name` (resolved at compile time of the *user*
/// crate, since `module_path!()` expands in place).
#[proc_macro_attribute]
pub fn parity(args: TokenStream, input: TokenStream) -> TokenStream {
    let item: ItemFn = parse_macro_input!(input as ItemFn);
    let fn_name = item.sig.ident.to_string();
    // We can't compute the path here because we don't know the user's
    // module path — `concat!` defers it until the user crate compiles.
    let impl_path_expr = quote! { concat!(module_path!(), "::", #fn_name) };

    // Reuse the same arg parser as the impl form by wrapping the bare
    // arg TokenStream into a fake attribute.
    let args2: TS2 = args.into();
    let attr: Attribute = syn::parse_quote!(#[parity(#args2)]);
    let submit = match parse_args(&attr) {
        Ok(parsed) => build_submit(&parsed, attr.span(), impl_path_expr, None)
            .unwrap_or_else(Error::into_compile_error),
        Err(e) => e.into_compile_error(),
    };

    // Original fn passes through unchanged; the submit sits beside it.
    let out = quote! {
        #item
        #submit
    };
    out.into()
}

/// Emit `inventory::submit! { ParityEntry { ... } }`.
///
/// `parent_path` is the enclosing impl's `path` value (if any). A child
/// `path` starting with `.` is rewritten at expansion time as
/// `parent_path + child`, producing a single `&'static str` literal in
/// the generated code (so the registered entry holds one string, not a
/// runtime `concat!`).
///
/// Returns a `syn::Error` instead of panicking so callers can convert it
/// into a `compile_error!` diagnostic with span info.
fn build_submit(
    args: &ParityArgs,
    span: proc_macro2::Span,
    impl_path_expr: TS2,
    parent_path: Option<&str>,
) -> Result<TS2, Error> {
    let path_lit = args.path.as_ref().ok_or_else(|| {
        Error::new(span, "parity: missing required `path = \"...\"`")
    })?;

    // Resolve relative paths against the parent. The leading `.` lets the
    // user write `.foo` instead of repeating the full prefix on every
    // method; this expansion happens at compile time so the runtime
    // entry holds the fully-qualified string.
    let path_value = path_lit.value();
    let path_lit = if let Some(suffix) = path_value.strip_prefix('.') {
        match parent_path {
            Some(parent) => LitStr::new(&format!("{parent}.{suffix}"), path_lit.span()),
            None => {
                return Err(Error::new(
                    path_lit.span(),
                    "parity: relative path (leading `.`) requires the enclosing \
                     `#[parity_impl(...)]` to declare a `path`",
                ));
            }
        }
    } else {
        path_lit.clone()
    };

    let status = args.status.as_ref().ok_or_else(|| {
        Error::new(
            span,
            "parity: missing required `status = Implemented | Partial | Unimplemented`",
        )
    })?;

    // `status` is parsed as a bare ident so it can appear as
    // `::api_parity_rs_core::Status::#status` (a path, not a string). Validate
    // here; an invalid one would otherwise produce a confusing
    // "no variant named X" error from rustc later.
    if status != "Implemented" && status != "Partial" && status != "Unimplemented" {
        return Err(Error::new(
            status.span(),
            format!(
                "parity: `status` must be one of `Implemented`, `Partial`, or `Unimplemented` (got `{status}`)"
            ),
        ));
    }

    // Force authors to justify Unimplemented stubs. The whole point of
    // a stub is that the comment surfaces the reason at the call site.
    if status == "Unimplemented" && args.comment.is_none() {
        return Err(Error::new(
            span,
            "parity: `status = Unimplemented` requires a `comment = \"...\"` explaining why",
        ));
    }

    // ParityEntry stores the optionals as Option<&'static str> / u32, so
    // we wrap each provided value in `Some(...)` and substitute `None`
    // otherwise.
    let since_tok = match &args.since {
        Some(s) => quote!(Some(#s)),
        None => quote!(None),
    };
    let comment_tok = match &args.comment {
        Some(s) => quote!(Some(#s)),
        None => quote!(None),
    };
    let issue_tok = match &args.issue {
        Some(i) => quote!(Some(#i)),
        None => quote!(None),
    };

    // Fully-qualified `::api_parity_rs_core::...` paths so this works no
    // matter what the user has imported.
    Ok(quote! {
        ::api_parity_rs_core::inventory::submit! {
            ::api_parity_rs_core::ParityEntry {
                path: #path_lit,
                implementation: #impl_path_expr,
                status: ::api_parity_rs_core::Status::#status,
                since: #since_tok,
                comment: #comment_tok,
                issue: #issue_tok,
            }
        }
    })
}
