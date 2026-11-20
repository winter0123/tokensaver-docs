// SPDX-License-Identifier: MIT
// Copyright (c) 2026 winter0123 and tokensaver-docs contributors
//
// Optional TUI companion: mirrors OpenCode's searchable /model picker without
// changing the chat model. Only TokenSaver-tagged model-selection forms are
// handled; all other question forms stay owned by OpenCode.
import { Plugin } from '@opencode/plugin/tui';

export function tokensaverModelForm(form) {
  if (!form || !Array.isArray(form.fields) || form.fields.length !== 1) return null;
  const field = form.fields[0];
  if (field?.type !== 'string' || typeof field.key !== 'string' ||
      !Array.isArray(field.options) || field.options.length === 0) return null;
  const title = String(form.title || '') + ' ' + String(field.title || '');
  if (!/TokenSaver\s*모델|TokenSaver\s*Docs.*(?:model|모델)/i.test(title))
    return null;
  const options = field.options.filter(option =>
    typeof option?.label === 'string' && option.label.trim() &&
    typeof (option?.value ?? option?.label) === 'string')
    .map(option => ({title:option.label,
      description:typeof option.description === 'string' ? option.description : undefined,
      value:option.value ?? option.label}));
  if (!options.length) return null;
  return {fieldKey:field.key,options};
}

export function searchTokensaverModels(query,options) {
  const normalized = String(query || '').normalize('NFKC').trim().toLocaleLowerCase();
  if (!normalized) return options;
  const words = normalized.split(/\s+/).filter(Boolean);
  return options.filter(option => words.every(word =>
    (option.title+' '+(option.description || '')).normalize('NFKC').toLocaleLowerCase().includes(word)));
}

export default Plugin.define({
  id:'tokensaver-docs.tui',
  setup(ctx) {
    const active = new Set();
    const cleanup = ctx.data.on('form.created', event => {
      const data = event?.data || {};
      const info = data.form || data;
      const sessionID = info.sessionID || data.sessionID;
      const formID = info.id || data.formID || data.id;
      if (typeof sessionID !== 'string' || typeof formID !== 'string' ||
          active.has(formID)) return;
      active.add(formID);
      void (async () => {
        // Forms may be listed before their cached reactive snapshot has
        // settled, so sync at the precise selected session+location.
        const location = event.location || ctx.location;
        await ctx.data.session.form.sync(sessionID,location);
        const forms = ctx.data.session.form.list(sessionID,location) || [];
        const form = forms.find(item => item.id === formID);
        const spec = tokensaverModelForm(form);
        if (!spec) return;
        const selected = await ctx.ui.dialog.select({
          title:'TokenSaver Docs · 이미지 모델 검색',
          placeholder:'모델명이나 제공자 검색',
          options:spec.options,
          search:searchTokensaverModels,
        });
        // Esc or a closed dialog cannot grant model selection.
        if (selected === undefined) return;
        if (!spec.options.some(item => item.value === selected)) return;
        await ctx.data.session.form.reply({
          sessionID,formID,answer:{[spec.fieldKey]:selected}
        },location);
        // The question tool receives the native form answer and continues
        // the suspended agent turn. Never send a new chat message.
      })().catch(() => {
        // The ordinary OpenCode form remains available if the TUI host
        // lacks this API or another window has already settled the form.
      }).finally(() => active.delete(formID));
    });
    return () => cleanup();
  },
});
