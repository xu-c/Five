create table public.five_pairs (
    code text primary key check (code ~ '^([0-9]{6}|[0-9]{10})$'),
    host_key uuid not null,
    guest_key uuid,
    offer text not null check (length(offer) between 1 and 8192),
    answer text check (length(answer) between 1 and 8192),
    expires_at timestamptz not null default (now() + interval '5 minutes')
);

alter table public.five_pairs enable row level security;
revoke all on public.five_pairs from public, anon, authenticated;
grant select, insert, update, delete on public.five_pairs to service_role;

create function public.five_create_pair(p_code text, p_host_key uuid, p_offer text)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
    perform pg_advisory_xact_lock(45812011);
    delete from public.five_pairs where expires_at <= now();
    if (select count(*) from public.five_pairs) >= 60 then
        return false;
    end if;
    insert into public.five_pairs(code, host_key, offer)
    values (p_code, p_host_key, p_offer) on conflict do nothing;
    return found;
end;
$$;

revoke all on function public.five_create_pair(text, uuid, text) from public, anon, authenticated;
grant execute on function public.five_create_pair(text, uuid, text) to service_role;
