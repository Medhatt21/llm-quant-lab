--
-- PostgreSQL database dump
--

\restrict TOGfl5zJdwRzClCmd3ujMvtFKT06FGH5yO93KA6Ddl5bdQKdUKUcSPgahd2W7KB

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: calibration_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.calibration_records (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    dataset_name character varying(100) NOT NULL,
    dataset_split character varying(50) DEFAULT 'train'::character varying,
    num_samples integer NOT NULL,
    sequence_length integer,
    data_hash character varying(64),
    seed integer,
    extra_metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: calibration_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.calibration_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: calibration_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.calibration_records_id_seq OWNED BY public.calibration_records.id;


--
-- Name: environment_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.environment_snapshots (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    python_version character varying(50),
    pytorch_version character varying(50),
    cuda_version character varying(50),
    rocm_version character varying(50),
    transformers_version character varying(50),
    lightcompress_version character varying(50),
    gpu_name character varying(255),
    gpu_driver character varying(100),
    gpu_count integer,
    cpu_model character varying(255),
    ram_gb double precision,
    pip_freeze text,
    git_sha character varying(40),
    git_branch character varying(255),
    git_diff_hash character varying(64),
    env_hash character varying(64)
);


--
-- Name: environment_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.environment_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: environment_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.environment_snapshots_id_seq OWNED BY public.environment_snapshots.id;


--
-- Name: experiment_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.experiment_groups (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    group_type character varying(50),
    metadata_json jsonb DEFAULT '{}'::jsonb
);


--
-- Name: experiment_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.experiment_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: experiment_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.experiment_groups_id_seq OWNED BY public.experiment_groups.id;


--
-- Name: experiments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.experiments (
    id integer NOT NULL,
    uuid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name character varying(255),
    description text,
    git_sha character varying(40),
    git_branch character varying(255),
    model_name character varying(255) NOT NULL,
    model_path text,
    base_precision character varying(20) DEFAULT 'fp16'::character varying,
    hardware_profile character varying(100),
    gpu_type character varying(100),
    gpu_count integer DEFAULT 1,
    status character varying(20) DEFAULT 'pending'::character varying,
    error_message text,
    notes text,
    tags text[],
    wandb_run_id character varying(50),
    wandb_run_url text,
    wandb_project character varying(100),
    config_hash character varying(64),
    environment_id integer,
    group_id integer,
    seed integer,
    CONSTRAINT experiments_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metrics (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    quant_config_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    dataset character varying(100) NOT NULL,
    split character varying(50) DEFAULT 'test'::character varying,
    metric_name character varying(100) NOT NULL,
    value double precision NOT NULL,
    extra_metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: quant_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quant_configs (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    method_name character varying(100) NOT NULL,
    method_version character varying(50),
    bit_width integer NOT NULL,
    per_channel boolean DEFAULT true,
    is_symmetric boolean DEFAULT true,
    group_size integer,
    activation_quant boolean DEFAULT false,
    activation_bits integer,
    kv_quant boolean DEFAULT false,
    kv_bits integer,
    stack_order integer DEFAULT 0,
    parent_config_id integer,
    config_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    calib_dataset character varying(100),
    calib_size integer,
    calib_seq_length integer,
    status character varying(20) DEFAULT 'pending'::character varying,
    error_message text,
    duration_seconds double precision,
    CONSTRAINT quant_configs_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'skipped'::character varying])::text[])))
);


--
-- Name: scientist_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scientist_reports (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    llm_model character varying(100),
    llm_provider character varying(100),
    prompt_payload_json jsonb NOT NULL,
    report_markdown text NOT NULL,
    summary text,
    pass_fail character varying(20),
    confidence_score double precision,
    reasoning_tags text[],
    key_findings text[],
    suggested_experiments text[],
    prompt_tokens integer,
    completion_tokens integer,
    total_tokens integer,
    extra_metadata jsonb DEFAULT '{}'::jsonb,
    CONSTRAINT scientist_reports_pass_fail_check CHECK (((pass_fail)::text = ANY ((ARRAY['pass'::character varying, 'fail'::character varying, 'inconclusive'::character varying, 'unknown'::character varying])::text[])))
);


--
-- Name: experiment_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.experiment_summary AS
 SELECT e.id,
    e.uuid,
    e.name,
    e.model_name,
    e.status,
    e.created_at,
    count(DISTINCT qc.id) AS num_configs,
    count(DISTINCT m.id) AS num_metrics,
    count(DISTINCT sr.id) AS num_reports,
    array_agg(DISTINCT qc.method_name) FILTER (WHERE (qc.method_name IS NOT NULL)) AS methods_used,
    min(m.value) FILTER (WHERE ((m.metric_name)::text = 'perplexity'::text)) AS best_perplexity
   FROM (((public.experiments e
     LEFT JOIN public.quant_configs qc ON ((e.id = qc.experiment_id)))
     LEFT JOIN public.metrics m ON ((e.id = m.experiment_id)))
     LEFT JOIN public.scientist_reports sr ON ((e.id = sr.experiment_id)))
  GROUP BY e.id, e.uuid, e.name, e.model_name, e.status, e.created_at;


--
-- Name: experiments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.experiments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: experiments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.experiments_id_seq OWNED BY public.experiments.id;


--
-- Name: hardware_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hardware_stats (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    quant_config_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    gpu_type character varying(100),
    gpu_memory_gb double precision,
    latency_p50 double precision,
    latency_p95 double precision,
    latency_p99 double precision,
    latency_mean double precision,
    latency_std double precision,
    tokens_per_second double precision,
    batch_size integer,
    sequence_length integer,
    memory_allocated double precision,
    memory_reserved double precision,
    memory_peak double precision,
    power_avg double precision,
    power_peak double precision,
    energy_joules double precision,
    model_size_mb double precision,
    quantized_size_mb double precision,
    compression_ratio double precision,
    extra_metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: hardware_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hardware_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hardware_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hardware_stats_id_seq OWNED BY public.hardware_stats.id;


--
-- Name: knowledge_edges; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.knowledge_edges (
    id integer NOT NULL,
    source_id character varying(100),
    target_id character varying(100),
    edge_type character varying(50) NOT NULL,
    strength double precision DEFAULT 0.5,
    metadata_json jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: knowledge_edges_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.knowledge_edges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: knowledge_edges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.knowledge_edges_id_seq OWNED BY public.knowledge_edges.id;


--
-- Name: knowledge_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.knowledge_nodes (
    id character varying(100) NOT NULL,
    label character varying(255) NOT NULL,
    node_type character varying(50) NOT NULL,
    category character varying(100),
    metadata_json jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: layer_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.layer_metrics (
    id integer NOT NULL,
    experiment_id integer NOT NULL,
    quant_config_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    layer_index integer NOT NULL,
    layer_name character varying(255),
    layer_type character varying(100),
    stat_name character varying(100) NOT NULL,
    stat_type character varying(50) DEFAULT 'weight'::character varying,
    value double precision NOT NULL,
    histogram_bins double precision[],
    histogram_counts integer[],
    extra_metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: layer_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.layer_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: layer_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.layer_metrics_id_seq OWNED BY public.layer_metrics.id;


--
-- Name: method_comparison; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.method_comparison AS
 SELECT qc.method_name,
    qc.bit_width,
    e.model_name,
    m.dataset,
    m.metric_name,
    avg(m.value) AS avg_value,
    min(m.value) AS min_value,
    max(m.value) AS max_value,
    count(*) AS num_experiments
   FROM ((public.quant_configs qc
     JOIN public.experiments e ON ((qc.experiment_id = e.id)))
     JOIN public.metrics m ON ((qc.id = m.quant_config_id)))
  WHERE ((e.status)::text = 'completed'::text)
  GROUP BY qc.method_name, qc.bit_width, e.model_name, m.dataset, m.metric_name;


--
-- Name: metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metrics_id_seq OWNED BY public.metrics.id;


--
-- Name: paper_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.paper_notes (
    id integer NOT NULL,
    paper_id character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    title text NOT NULL,
    authors text[],
    year integer,
    venue character varying(255),
    arxiv_id character varying(50),
    doi character varying(100),
    citation text,
    core_idea text,
    relevant_equations text,
    expected_behavior text,
    known_limitations text,
    method_names text[],
    tags text[],
    extra_metadata jsonb DEFAULT '{}'::jsonb
);


--
-- Name: paper_notes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.paper_notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: paper_notes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.paper_notes_id_seq OWNED BY public.paper_notes.id;


--
-- Name: quant_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.quant_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: quant_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.quant_configs_id_seq OWNED BY public.quant_configs.id;


--
-- Name: scientist_reports_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scientist_reports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scientist_reports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scientist_reports_id_seq OWNED BY public.scientist_reports.id;


--
-- Name: wandb_sync_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wandb_sync_log (
    id integer NOT NULL,
    experiment_id integer,
    sync_direction character varying(10),
    sync_type character varying(50),
    synced_at timestamp with time zone DEFAULT now(),
    status character varying(20) DEFAULT 'success'::character varying,
    details jsonb DEFAULT '{}'::jsonb
);


--
-- Name: wandb_sync_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.wandb_sync_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: wandb_sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.wandb_sync_log_id_seq OWNED BY public.wandb_sync_log.id;


--
-- Name: calibration_records id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calibration_records ALTER COLUMN id SET DEFAULT nextval('public.calibration_records_id_seq'::regclass);


--
-- Name: environment_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environment_snapshots ALTER COLUMN id SET DEFAULT nextval('public.environment_snapshots_id_seq'::regclass);


--
-- Name: experiment_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiment_groups ALTER COLUMN id SET DEFAULT nextval('public.experiment_groups_id_seq'::regclass);


--
-- Name: experiments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiments ALTER COLUMN id SET DEFAULT nextval('public.experiments_id_seq'::regclass);


--
-- Name: hardware_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hardware_stats ALTER COLUMN id SET DEFAULT nextval('public.hardware_stats_id_seq'::regclass);


--
-- Name: knowledge_edges id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_edges ALTER COLUMN id SET DEFAULT nextval('public.knowledge_edges_id_seq'::regclass);


--
-- Name: layer_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layer_metrics ALTER COLUMN id SET DEFAULT nextval('public.layer_metrics_id_seq'::regclass);


--
-- Name: metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrics ALTER COLUMN id SET DEFAULT nextval('public.metrics_id_seq'::regclass);


--
-- Name: paper_notes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_notes ALTER COLUMN id SET DEFAULT nextval('public.paper_notes_id_seq'::regclass);


--
-- Name: quant_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quant_configs ALTER COLUMN id SET DEFAULT nextval('public.quant_configs_id_seq'::regclass);


--
-- Name: scientist_reports id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scientist_reports ALTER COLUMN id SET DEFAULT nextval('public.scientist_reports_id_seq'::regclass);


--
-- Name: wandb_sync_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wandb_sync_log ALTER COLUMN id SET DEFAULT nextval('public.wandb_sync_log_id_seq'::regclass);


--
-- Data for Name: calibration_records; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.calibration_records (id, experiment_id, created_at, dataset_name, dataset_split, num_samples, sequence_length, data_hash, seed, extra_metadata) FROM stdin;
\.


--
-- Data for Name: environment_snapshots; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.environment_snapshots (id, created_at, python_version, pytorch_version, cuda_version, rocm_version, transformers_version, lightcompress_version, gpu_name, gpu_driver, gpu_count, cpu_model, ram_gb, pip_freeze, git_sha, git_branch, git_diff_hash, env_hash) FROM stdin;
\.


--
-- Data for Name: experiment_groups; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.experiment_groups (id, created_at, name, description, group_type, metadata_json) FROM stdin;
\.


--
-- Data for Name: experiments; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.experiments (id, uuid, created_at, updated_at, name, description, git_sha, git_branch, model_name, model_path, base_precision, hardware_profile, gpu_type, gpu_count, status, error_message, notes, tags, wandb_run_id, wandb_run_url, wandb_project, config_hash, environment_id, group_id, seed) FROM stdin;
2108	c55df0f5-1917-4961-aa7a-4caaa52f9bc6	2026-03-03 16:58:52.956226+00	2026-03-03 17:03:05.034979+00	opt-350m RTN 4bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	kpzjo1su	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/kpzjo1su	llm-quant-lab	\N	\N	\N	\N
2096	51ca784d-c45c-4d86-95a0-af92d80395d1	2026-03-03 16:58:52.922682+00	2026-03-03 18:15:58.664756+00	opt-30b GPTQ 4bit	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	h923nagp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/h923nagp	llm-quant-lab	\N	\N	\N	\N
2105	789938ef-9b0a-4cdd-9c4a-abc6fd8515f5	2026-03-03 16:58:52.949048+00	2026-03-03 18:28:38.299143+00	opt-30b GPTQ 3bit	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	uz32qdqt	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/uz32qdqt	llm-quant-lab	\N	\N	\N	\N
2118	033e22e6-51d9-4576-97f3-e1d620c7e959	2026-03-03 16:58:52.971704+00	2026-03-03 17:18:43.353229+00	bloom-3b GPTQ 4bit	\N	\N	\N	bigscience/bloom-3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	5ubzq1uk	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5ubzq1uk	llm-quant-lab	\N	\N	\N	\N
2090	47d2faa4-cf79-4b43-ac1b-65629dd3ed5c	2026-03-03 16:58:52.892718+00	2026-03-03 17:03:53.097181+00	opt-125m GPTQ 4bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	oq7x1eki	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/oq7x1eki	llm-quant-lab	\N	\N	\N	\N
2110	f9bfebc6-fdff-4833-97c3-6fad0baa53ee	2026-03-03 16:58:52.959639+00	2026-03-03 17:04:11.861284+00	opt-2.7b RTN 4bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	uikogllg	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/uikogllg	llm-quant-lab	\N	\N	\N	\N
2127	721d5321-3ee6-480a-9c82-e654dd02c8b1	2026-03-03 16:58:52.986076+00	2026-03-03 17:24:46.574608+00	Llama-2-7b-hf SMOOTHQUANT 8bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	hyojvzm6	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hyojvzm6	llm-quant-lab	\N	\N	\N	\N
2092	72d501c4-7dc2-4ef9-b27b-a79f8c42a2e9	2026-03-03 16:58:52.909624+00	2026-03-03 17:04:21.800762+00	opt-1.3b GPTQ 4bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	sfhbx2oa	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/sfhbx2oa	llm-quant-lab	\N	\N	\N	\N
2094	edc93bee-15b5-4791-836b-9e003359acf3	2026-03-03 16:58:52.916784+00	2026-03-03 17:24:48.944256+00	opt-6.7b GPTQ 4bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	lgdd1ubn	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/lgdd1ubn	llm-quant-lab	\N	\N	\N	\N
2111	156a9673-56f7-4104-9386-d996ba59045f	2026-03-03 16:58:52.961225+00	2026-03-03 17:04:23.26706+00	opt-6.7b RTN 4bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	cm2unhwl	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cm2unhwl	llm-quant-lab	\N	\N	\N	\N
2126	0c59f0d3-b051-4a6e-809d-316ce832d3d3	2026-03-03 16:58:52.984349+00	2026-03-03 17:26:04.458197+00	llama-13b SMOOTHQUANT 8bit	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	wpni5uu5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/wpni5uu5	llm-quant-lab	\N	\N	\N	\N
2132	bd014048-e74c-45e1-883b-34e5de3811be	2026-03-03 16:58:52.993328+00	2026-03-03 17:26:11.987019+00	Mistral-7B-v0.1 SMOOTHQUANT 8bit	\N	\N	\N	mistralai/Mistral-7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	nwj5dkyp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nwj5dkyp	llm-quant-lab	\N	\N	\N	\N
2208	3a5fb02d-afe6-4e46-b6f1-778fede66bce	2026-03-03 22:34:54.488767+00	2026-03-03 22:37:32.561172+00	opt-30b RTN 4bit retry	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	cmqxeque	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cmqxeque	llm-quant-lab	\N	\N	\N	\N
2119	8b1d66c1-942a-4cb3-8f1f-7a3c2aaf5197	2026-03-03 16:58:52.973139+00	2026-03-03 17:34:54.37005+00	bloom-7b1 GPTQ 4bit	\N	\N	\N	bigscience/bloom-7b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	s4bzcajc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/s4bzcajc	llm-quant-lab	\N	\N	\N	\N
2135	e9c1680d-a6c8-4508-bfdf-ef10bd76e161	2026-03-03 16:58:52.997809+00	2026-03-03 17:37:21.068922+00	Llama-2-7b-hf GPTQ 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	ihh6i4qb	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ihh6i4qb	llm-quant-lab	\N	\N	\N	\N
2151	9db7f468-802d-4ebb-8738-41326b3aeaa9	2026-03-03 16:58:53.021999+00	2026-03-03 17:38:37.074862+00	opt-6.7b LLMINT8 8bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	vzg4hmvr	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/vzg4hmvr	llm-quant-lab	\N	\N	\N	\N
2255	9eb164f7-f131-407b-8f0e-53b000695132	2026-03-03 22:35:03.688703+00	2026-03-03 23:24:59.816442+00	opt-1.3b FP16 baseline	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	11tol67m	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/11tol67m	llm-quant-lab	\N	\N	\N	\N
2112	c68e8de2-832b-4cd0-8a03-4ef100081d2b	2026-03-03 16:58:52.96279+00	2026-03-03 17:06:36.522468+00	opt-13b RTN 4bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	rxyso9vs	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/rxyso9vs	llm-quant-lab	\N	\N	\N	\N
2093	d1ea733e-1441-4e4e-8e14-55dbdd838800	2026-03-03 16:58:52.912817+00	2026-03-03 17:07:19.186208+00	opt-2.7b GPTQ 4bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	9al6ccye	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9al6ccye	llm-quant-lab	\N	\N	\N	\N
2101	3dcc7d0d-7f7a-4e3f-970e-7d72c7ced2c6	2026-03-03 16:58:52.938236+00	2026-03-03 17:07:42.226789+00	opt-1.3b GPTQ 3bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	v0f6deox	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/v0f6deox	llm-quant-lab	\N	\N	\N	\N
2116	5a248d0f-05ae-43db-9a85-3fe25a145dbf	2026-03-03 16:58:52.96883+00	2026-03-03 17:07:47.509941+00	bloom-1b1 GPTQ 4bit	\N	\N	\N	bigscience/bloom-1b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	zik6fwex	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/zik6fwex	llm-quant-lab	\N	\N	\N	\N
2107	bb9fa8fc-ce5b-4e2b-b4f9-9e58575d30f0	2026-03-03 16:58:52.954562+00	2026-03-03 17:01:20.627949+00	opt-125m RTN 4bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	ney77ctd	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ney77ctd	llm-quant-lab	\N	\N	\N	\N
2100	a7af531f-b878-4988-a6b0-975cb1ced3e2	2026-03-03 16:58:52.935521+00	2026-03-03 17:01:51.083916+00	opt-350m GPTQ 3bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	oxi7c0dx	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/oxi7c0dx	llm-quant-lab	\N	\N	\N	\N
2117	0e19ab7c-e248-416a-9523-4e9fa11d3aea	2026-03-03 16:58:52.970278+00	2026-03-03 17:09:47.389541+00	bloom-1b7 GPTQ 4bit	\N	\N	\N	bigscience/bloom-1b7	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	6zdx1na3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/6zdx1na3	llm-quant-lab	\N	\N	\N	\N
2124	1d178587-86ac-40b7-86fe-4b208b4c5236	2026-03-03 16:58:52.981442+00	2026-03-03 17:13:30.234396+00	opt-iml-30b LLMINT8 8bit	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	paoeiw89	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/paoeiw89	llm-quant-lab	\N	\N	\N	\N
2125	3a378fc5-48a9-4510-8661-a00ad3bd6113	2026-03-03 16:58:52.98289+00	2026-03-03 17:15:04.746009+00	llama-7b SMOOTHQUANT 8bit	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	0tvny906	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/0tvny906	llm-quant-lab	\N	\N	\N	\N
2130	3ad4657b-3e68-4838-806a-7c77bef04f34	2026-03-03 16:58:52.990369+00	2026-03-03 17:15:54.205991+00	falcon-7b SMOOTHQUANT 8bit	\N	\N	\N	tiiuae/falcon-7b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,reproduce-all}	vkr80ivb	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/vkr80ivb	llm-quant-lab	\N	\N	\N	\N
2152	e0b1ad2d-dd6f-43f7-b7e5-87f9fc20c7b7	2026-03-03 16:58:53.023463+00	2026-03-03 17:39:16.080149+00	opt-13b LLMINT8 8bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	myeav8vl	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/myeav8vl	llm-quant-lab	\N	\N	\N	\N
2226	121eeb2f-7459-44b8-9eaa-8f9cef61c1e4	2026-03-03 22:35:03.623354+00	2026-03-03 22:52:02.666553+00	opt-66b FP16 baseline	\N	\N	\N	facebook/opt-66b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	ietvmwkv	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ietvmwkv	llm-quant-lab	\N	\N	\N	\N
2095	ad1cc66b-735b-4be6-8dad-6dd89b82acd8	2026-03-03 16:58:52.919854+00	2026-03-03 17:39:39.883798+00	opt-13b GPTQ 4bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	q7xonobq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/q7xonobq	llm-quant-lab	\N	\N	\N	\N
2133	6ab50d92-5c5b-4e71-bfbe-b3b85982372a	2026-03-03 16:58:52.994919+00	2026-03-03 17:42:33.140388+00	Mixtral-8x7B-v0.1 SMOOTHQUANT 8bit	\N	\N	\N	mistralai/Mixtral-8x7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	qd1pwhug	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/qd1pwhug	llm-quant-lab	\N	\N	\N	\N
2123	332b332c-16a7-47f8-a050-a979d5b0af56	2026-03-03 16:58:52.979201+00	2026-03-03 17:52:42.479877+00	opt-iml-30b SMOOTHQUANT_O3 8bit	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	6sjeaf21	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/6sjeaf21	llm-quant-lab	\N	\N	\N	\N
2097	e42bf41f-6f7a-4200-80d8-7e39fdd1cea5	2026-03-03 16:58:52.925594+00	2026-03-03 19:06:09.192544+00	opt-66b GPTQ 4bit	\N	\N	\N	facebook/opt-66b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	syun4cjo	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/syun4cjo	llm-quant-lab	\N	\N	\N	\N
2146	ef0a5d32-74d8-446c-a288-22988373df02	2026-03-03 16:58:53.014541+00	2026-03-03 19:12:26.377304+00	Mixtral-8x7B-Instruct-v0.1 AWQ 4bit	\N	\N	\N	mistralai/Mixtral-8x7B-Instruct-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	cgewzgmq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cgewzgmq	llm-quant-lab	\N	\N	\N	\N
2147	e20e4f36-bc94-49b5-b7ee-dc3f93d9d039	2026-03-03 16:58:53.016001+00	2026-03-03 19:46:38.442853+00	Mistral-7B-Instruct-v0.2 AWQ 4bit	\N	\N	\N	mistralai/Mistral-7B-Instruct-v0.2	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	ywt2l4q3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ywt2l4q3	llm-quant-lab	\N	\N	\N	\N
2139	b785a047-4447-46cc-b4cb-858f520f8e12	2026-03-03 16:58:53.004072+00	2026-03-03 19:57:55.235836+00	llama-7b AWQ 4bit	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	hb7jw2ho	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hb7jw2ho	llm-quant-lab	\N	\N	\N	\N
2143	2d4cd720-ef11-434a-a3a9-76eed3d1784e	2026-03-03 16:58:53.009955+00	2026-03-03 20:43:07.264087+00	Llama-2-7b-hf AWQ 3bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	9ay0ql9w	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9ay0ql9w	llm-quant-lab	\N	\N	\N	\N
2140	23151f53-14ed-4454-b34f-55ccf0e8af31	2026-03-03 16:58:53.00559+00	2026-03-03 20:43:36.947783+00	llama-13b AWQ 4bit	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	ociaexr9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ociaexr9	llm-quant-lab	\N	\N	\N	\N
2134	bf1e2068-a53b-4964-a62c-316a53905719	2026-03-03 16:58:52.996369+00	2026-03-03 21:52:51.855403+00	Llama-2-7b-hf AWQ 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	zmsa2eca	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/zmsa2eca	llm-quant-lab	\N	\N	\N	\N
2142	9d92ddcd-2387-496e-9909-b1cbc3ae6d9f	2026-03-03 16:58:53.008504+00	2026-03-03 22:30:36.934335+00	llama-65b AWQ 4bit	\N	\N	\N	huggyllama/llama-65b	\N	fp16	\N	\N	1	failed	Experiment orphaned (container restarted while running)	\N	{paper:awq,reproduce-all}	e64zeqkp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/e64zeqkp	llm-quant-lab	\N	\N	\N	\N
2091	914ea773-4b7c-41e8-b919-c6683936259e	2026-03-03 16:58:52.906285+00	2026-03-03 17:03:31.796941+00	opt-350m GPTQ 4bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	y8966xid	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/y8966xid	llm-quant-lab	\N	\N	\N	\N
2109	d81d6f6d-a83a-4f9a-92e5-7b8a42a47ef1	2026-03-03 16:58:52.957837+00	2026-03-03 17:03:42.542372+00	opt-1.3b RTN 4bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	kkfsm0rf	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/kkfsm0rf	llm-quant-lab	\N	\N	\N	\N
2131	a68cfbf0-2dd7-49fc-b8cd-1a55d9f427e8	2026-03-03 16:58:52.991812+00	2026-03-03 17:17:04.843997+00	falcon-40b SMOOTHQUANT 8bit	\N	\N	\N	tiiuae/falcon-40b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,reproduce-all}	8bprt2vg	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/8bprt2vg	llm-quant-lab	\N	\N	\N	\N
2115	412cecd2-c1e4-4160-bffd-535703ef146b	2026-03-03 16:58:52.967134+00	2026-03-03 17:07:11.294747+00	bloom-560m GPTQ 4bit	\N	\N	\N	bigscience/bloom-560m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	f7i5rf3v	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/f7i5rf3v	llm-quant-lab	\N	\N	\N	\N
2098	df01d6a0-6626-43b1-ab67-b6e65a8c9f09	2026-03-03 16:58:52.928329+00	2026-03-03 16:59:08.500186+00	opt-175b GPTQ 4bit	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:gptq,reproduce-all}	4psz4b3m	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/4psz4b3m	llm-quant-lab	\N	\N	\N	\N
2106	b6a096bc-5a42-4f0b-9c49-923161cb502c	2026-03-03 16:58:52.951728+00	2026-03-03 16:59:20.967818+00	opt-175b GPTQ 3bit	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:gptq,reproduce-all}	82z0kvl1	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/82z0kvl1	llm-quant-lab	\N	\N	\N	\N
2099	540c590d-9bb1-4f2a-80b0-91755573df60	2026-03-03 16:58:52.931887+00	2026-03-03 17:01:54.781364+00	opt-125m GPTQ 3bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	m23rzsgj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m23rzsgj	llm-quant-lab	\N	\N	\N	\N
2102	58de15ef-8276-4ad7-aac2-c3efbca63563	2026-03-03 16:58:52.940826+00	2026-03-03 17:14:57.172302+00	opt-2.7b GPTQ 3bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	noos45qc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/noos45qc	llm-quant-lab	\N	\N	\N	\N
2136	33d7986b-ffc1-49f4-9832-7a25b86ed9a0	2026-03-03 16:58:52.99925+00	2026-03-03 17:20:21.692511+00	Llama-2-7b-hf RTN 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	e997rwi2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/e997rwi2	llm-quant-lab	\N	\N	\N	\N
2103	28ec5b3a-2872-4b77-9aa4-480dda978f12	2026-03-03 16:58:52.943603+00	2026-03-03 17:29:35.41927+00	opt-6.7b GPTQ 3bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	zu55fh8d	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/zu55fh8d	llm-quant-lab	\N	\N	\N	\N
2148	b0dec4a6-667e-4aa6-933e-d8cbed555c94	2026-03-03 16:58:53.017464+00	2026-03-03 17:35:49.37632+00	opt-125m LLMINT8 8bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	7w839wqd	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/7w839wqd	llm-quant-lab	\N	\N	\N	\N
2149	2ed1ee2c-34d6-454f-88b3-1f9da9a945fb	2026-03-03 16:58:53.018899+00	2026-03-03 17:36:30.058773+00	opt-1.3b LLMINT8 8bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	vaojwqrs	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/vaojwqrs	llm-quant-lab	\N	\N	\N	\N
2150	d3f8ba28-98b2-4a16-ac47-3b4da7855854	2026-03-03 16:58:53.020355+00	2026-03-03 17:37:33.217934+00	opt-2.7b LLMINT8 8bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	325iraxe	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/325iraxe	llm-quant-lab	\N	\N	\N	\N
2114	c4141135-c622-4b7b-8085-96b4d8061e41	2026-03-03 16:58:52.965714+00	2026-03-03 17:04:36.524472+00	opt-175b RTN 4bit	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:gptq,reproduce-all}	zvywgljj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/zvywgljj	llm-quant-lab	\N	\N	\N	\N
2113	923dd30c-aecc-49e3-bcff-a7368c087500	2026-03-03 16:58:52.964257+00	2026-03-03 17:04:41.65947+00	opt-30b RTN 4bit	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 98.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 6.25 GiB is allocated by PyTorch, and 41.79 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:gptq,reproduce-all}	q70ymhv1	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/q70ymhv1	llm-quant-lab	\N	\N	\N	\N
2121	bd6e7fe6-cb0c-4661-acc0-1b16b052f3ee	2026-03-03 16:58:52.975985+00	2026-03-03 17:07:33.124999+00	opt-175b SMOOTHQUANT_O1 8bit	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:smoothquant,reproduce-all}	dn8xg0k8	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/dn8xg0k8	llm-quant-lab	\N	\N	\N	\N
2122	2b984720-e701-4110-9f06-a696f6cd3d5d	2026-03-03 16:58:52.977709+00	2026-03-03 17:07:43.287498+00	opt-175b LLMINT8 8bit	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:smoothquant,reproduce-all}	8ifqspir	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/8ifqspir	llm-quant-lab	\N	\N	\N	\N
2129	31a8c1b4-3c91-46ea-b588-f7183935b1df	2026-03-03 16:58:52.988927+00	2026-03-03 17:15:33.858983+00	Llama-2-70b-hf SMOOTHQUANT 8bit	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 448.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 56.00 MiB is free. Of the allocated memory 10.54 GiB is allocated by PyTorch, and 91.80 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:smoothquant,reproduce-all}	l6sxu86d	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/l6sxu86d	llm-quant-lab	\N	\N	\N	\N
2128	baf5e340-e762-411e-810f-6896553e8d08	2026-03-03 16:58:52.987518+00	2026-03-03 17:16:07.919792+00	Llama-2-13b-hf SMOOTHQUANT 8bit	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 54.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 43.05 GiB is allocated by PyTorch, and 2.96 GiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:smoothquant,reproduce-all}	f0tgant4	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/f0tgant4	llm-quant-lab	\N	\N	\N	\N
2120	c12f7135-b64b-4467-88a4-2ce71675a30c	2026-03-03 16:58:52.974552+00	2026-03-03 17:17:41.20377+00	bloom GPTQ 4bit	\N	\N	\N	bigscience/bloom	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 392.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 180.00 MiB is free. Of the allocated memory 108.73 GiB is allocated by PyTorch, and 385.55 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:gptq,reproduce-all}	mr1algz9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mr1algz9	llm-quant-lab	\N	\N	\N	\N
2137	83c7b0b7-548e-478e-b649-478c5f94f0bd	2026-03-03 16:58:53.000683+00	2026-03-03 17:20:59.017087+00	Llama-2-13b-hf AWQ 4bit	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 136.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 10.20 GiB is allocated by PyTorch, and 14.68 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,reproduce-all}	nb1pwmcz	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nb1pwmcz	llm-quant-lab	\N	\N	\N	\N
2141	98a68149-7b26-44c1-b9ee-774f08766667	2026-03-03 16:58:53.007048+00	2026-03-03 17:29:31.466565+00	llama-30b AWQ 4bit	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 86.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 56.28 GiB is allocated by PyTorch, and 13.58 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,reproduce-all}	9e1tapw5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9e1tapw5	llm-quant-lab	\N	\N	\N	\N
2104	169edd03-294b-46f2-9dbf-2311c0dab2e6	2026-03-03 16:58:52.946553+00	2026-03-03 17:32:45.391735+00	opt-13b GPTQ 3bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	9rw6wbcz	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9rw6wbcz	llm-quant-lab	\N	\N	\N	\N
2145	fa936e48-197b-4a73-b465-3e8e12a1433d	2026-03-03 16:58:53.013064+00	2026-03-03 17:33:38.037783+00	Llama-2-70b-hf AWQ 3bit	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 448.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 10.54 GiB is allocated by PyTorch, and 63.80 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,reproduce-all}	7gkcg8zh	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/7gkcg8zh	llm-quant-lab	\N	\N	\N	\N
2242	ca453a09-007e-4095-8322-be9105adf1c6	2026-03-03 22:35:03.659075+00	2026-03-03 23:03:33.770949+00	falcon-40b FP16 baseline	\N	\N	\N	tiiuae/falcon-40b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,baseline,fp16}	6mlno05p	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/6mlno05p	llm-quant-lab	\N	\N	\N	\N
2527	2bdb4490-93d2-49ff-8cf6-65095c4eada9	2026-03-04 08:59:45.953047+00	2026-03-04 13:53:46.550394+00	opt-1.3b GPTQ 4bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	ejr88q7n	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ejr88q7n	llm-quant-lab	\N	\N	\N	\N
2213	654f8f52-6b36-4e35-b520-08e4c3d2ecb1	2026-03-03 22:34:54.543082+00	2026-03-04 05:11:56.814576+00	Llama-2-70b-hf AWQ 4bit retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	yssoqpaa	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/yssoqpaa	llm-quant-lab	\N	\N	\N	\N
2215	34fb8be6-d1fb-44e8-8f85-9213959c4522	2026-03-03 22:34:54.560836+00	2026-03-04 06:46:14.238159+00	llama-65b AWQ 4bit retry	\N	\N	\N	huggyllama/llama-65b	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	3x4384if	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/3x4384if	llm-quant-lab	\N	\N	\N	\N
2138	dae398ba-2796-490b-bd85-152c7610528b	2026-03-03 16:58:53.002147+00	2026-03-03 17:33:56.278702+00	Llama-2-70b-hf AWQ 4bit	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 448.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 266.00 MiB is free. Of the allocated memory 130.81 GiB is allocated by PyTorch, and 512.60 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,reproduce-all}	s4ul1tdw	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/s4ul1tdw	llm-quant-lab	\N	\N	\N	\N
2153	4156736d-48e8-4688-8dfd-f2e06f1d8079	2026-03-03 16:58:53.024954+00	2026-03-03 17:39:13.552006+00	Llama-3.1-8B GPTQ 2bit	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 112.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 10.71 GiB is allocated by PyTorch, and 15.66 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:paretoq,reproduce-all}	xnwlpi0h	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/xnwlpi0h	llm-quant-lab	\N	\N	\N	\N
2144	2bb6b9cd-694d-432b-9b78-9d5cd6f1f512	2026-03-03 16:58:53.011397+00	2026-03-03 18:16:16.906303+00	Llama-2-13b-hf AWQ 3bit	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 5.00 GiB. GPU 0 has a total capacity of 191.98 GiB of which 1016.00 MiB is free. Of the allocated memory 22.30 GiB is allocated by PyTorch, and 2.04 GiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,reproduce-all}	kdqydqlp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/kdqydqlp	llm-quant-lab	\N	\N	\N	\N
2239	65132495-6f21-4801-8aa6-63b2ffaf77b4	2026-03-03 22:35:03.652397+00	2026-03-03 23:00:57.775694+00	Llama-2-13b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	sbubircg	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/sbubircg	llm-quant-lab	\N	\N	\N	\N
2241	007a3925-bb87-4e38-9b8f-d5d06d624d28	2026-03-03 22:35:03.656862+00	2026-03-03 23:01:44.053404+00	falcon-7b FP16 baseline	\N	\N	\N	tiiuae/falcon-7b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,baseline,fp16}	30mxhvwu	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/30mxhvwu	llm-quant-lab	\N	\N	\N	\N
2235	d517361f-c594-49e8-8b2f-fa7da25d86e6	2026-03-03 22:35:03.643438+00	2026-03-03 23:02:09.45291+00	opt-iml-30b FP16 baseline	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	llvq2js3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/llvq2js3	llm-quant-lab	\N	\N	\N	\N
2240	078cb40c-9beb-43ed-b4e3-623d3c54ea4f	2026-03-03 22:35:03.654694+00	2026-03-03 23:05:41.215897+00	Llama-2-70b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	m93trfm4	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m93trfm4	llm-quant-lab	\N	\N	\N	\N
2258	f53a7ac6-91eb-4062-94be-41be23ba19d1	2026-03-03 22:35:03.695401+00	2026-03-03 23:27:53.236535+00	opt-13b FP16 baseline	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	dkc3bocj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/dkc3bocj	llm-quant-lab	\N	\N	\N	\N
2216	f24c423e-0f3d-4cc3-bfdf-90271ec2be42	2026-03-03 22:34:54.568702+00	2026-03-04 02:15:12.306406+00	Llama-2-13b-hf AWQ 3bit retry	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	wfzr5dvu	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/wfzr5dvu	llm-quant-lab	\N	\N	\N	\N
2219	de061819-27e0-4a98-85f2-6749db5b61d0	2026-03-03 22:35:03.605563+00	2026-03-03 22:40:00.431037+00	opt-125m FP16 baseline	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	gor1izhe	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/gor1izhe	llm-quant-lab	\N	\N	\N	\N
2220	94a6cca4-5eb1-4865-87a9-435e18154b93	2026-03-03 22:35:03.609025+00	2026-03-03 22:40:28.188198+00	opt-350m FP16 baseline	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	tob4uyjk	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/tob4uyjk	llm-quant-lab	\N	\N	\N	\N
2221	cd899cb7-8d72-4688-b4d9-fbfa46a98874	2026-03-03 22:35:03.611505+00	2026-03-03 22:40:55.285626+00	opt-1.3b FP16 baseline	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	cnsnh1zq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cnsnh1zq	llm-quant-lab	\N	\N	\N	\N
2222	e7a07b29-b742-438a-8a5e-47d725c74afc	2026-03-03 22:35:03.613983+00	2026-03-03 22:41:47.416732+00	opt-2.7b FP16 baseline	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	3gmaag5i	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/3gmaag5i	llm-quant-lab	\N	\N	\N	\N
2224	c51b8235-0b89-4964-bce4-a0d582974a35	2026-03-03 22:35:03.618688+00	2026-03-03 22:43:50.816813+00	opt-13b FP16 baseline	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	hokx8g0j	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hokx8g0j	llm-quant-lab	\N	\N	\N	\N
2225	34e1c65f-7a7a-40ae-a265-68ab3cba348b	2026-03-03 22:35:03.621113+00	2026-03-03 22:45:50.122928+00	opt-30b FP16 baseline	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	mnqrry35	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mnqrry35	llm-quant-lab	\N	\N	\N	\N
2228	c52c50e6-11b6-4d95-89a2-24fc340e6664	2026-03-03 22:35:03.627902+00	2026-03-03 22:52:54.301431+00	bloom-560m FP16 baseline	\N	\N	\N	bigscience/bloom-560m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	8sx3qmm4	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/8sx3qmm4	llm-quant-lab	\N	\N	\N	\N
2229	257da6c1-777a-4a82-ba2e-e453e9450e9a	2026-03-03 22:35:03.630154+00	2026-03-03 22:53:40.392416+00	bloom-1b1 FP16 baseline	\N	\N	\N	bigscience/bloom-1b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	nks47ynb	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nks47ynb	llm-quant-lab	\N	\N	\N	\N
2230	5d84437f-8210-4b28-9aeb-934161c847e4	2026-03-03 22:35:03.632351+00	2026-03-03 22:54:17.967177+00	bloom-1b7 FP16 baseline	\N	\N	\N	bigscience/bloom-1b7	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	4hfb1j9v	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/4hfb1j9v	llm-quant-lab	\N	\N	\N	\N
2231	2d2cd070-601d-40e7-8e67-b7bd8311cbc7	2026-03-03 22:35:03.634619+00	2026-03-03 22:55:07.210878+00	bloom-3b FP16 baseline	\N	\N	\N	bigscience/bloom-3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	t0nxv0fe	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/t0nxv0fe	llm-quant-lab	\N	\N	\N	\N
2232	f24e5add-25ef-47a4-9cb5-40b90eb56f79	2026-03-03 22:35:03.636778+00	2026-03-03 22:55:38.198013+00	bloom-7b1 FP16 baseline	\N	\N	\N	bigscience/bloom-7b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	cm70b4uu	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cm70b4uu	llm-quant-lab	\N	\N	\N	\N
2236	032d1cd7-f795-408e-a840-71f4ffa964a7	2026-03-03 22:35:03.645679+00	2026-03-03 22:56:54.160108+00	llama-7b FP16 baseline	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	xwi4dyyh	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/xwi4dyyh	llm-quant-lab	\N	\N	\N	\N
2238	ad6073cc-feb3-43d8-9ecf-ca8e5aed707e	2026-03-03 22:35:03.650141+00	2026-03-03 23:00:03.829014+00	Llama-2-7b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	pt453t33	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/pt453t33	llm-quant-lab	\N	\N	\N	\N
2217	5c8803f6-deeb-42bf-940e-0acfee343f53	2026-03-03 22:34:54.576344+00	2026-03-03 22:38:33.228778+00	Llama-2-70b-hf AWQ 3bit retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 448.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 66.00 MiB is free. Of the allocated memory 1000.02 MiB is allocated by PyTorch, and 1.98 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{reproduce-all,retry}	uhctusxv	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/uhctusxv	llm-quant-lab	\N	\N	\N	\N
2227	129a97ee-3ea8-40a9-8031-75f550795e0c	2026-03-03 22:35:03.625596+00	2026-03-03 22:52:27.699753+00	opt-175b FP16 baseline	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:gptq,baseline,fp16}	ap78c1sd	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ap78c1sd	llm-quant-lab	\N	\N	\N	\N
2234	44290de2-1ad1-4b52-a597-969fa128302f	2026-03-03 22:35:03.641171+00	2026-03-03 22:55:52.60706+00	opt-175b FP16 baseline	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:smoothquant,baseline,fp16}	40b065h6	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/40b065h6	llm-quant-lab	\N	\N	\N	\N
2233	0660efee-ca40-4a87-bd05-0de132b2ef2f	2026-03-03 22:35:03.638985+00	2026-03-03 22:59:12.569776+00	bloom FP16 baseline	\N	\N	\N	bigscience/bloom	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 1.15 GiB. GPU 0 has a total capacity of 191.98 GiB of which 674.00 MiB is free. Of the allocated memory 182.62 GiB is allocated by PyTorch, and 315.75 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:gptq,baseline,fp16}	1hij17yg	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/1hij17yg	llm-quant-lab	\N	\N	\N	\N
2262	4a770bfe-8809-48a7-981c-19444db0530c	2026-03-04 07:06:59.597859+00	2026-03-04 07:09:17.487907+00	opt-30b RTN 4bit retry2	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry2}	a4v1xys2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/a4v1xys2	llm-quant-lab	\N	\N	\N	\N
2529	0e232976-cc71-4eff-8438-8c2d2e0cd854	2026-03-04 08:59:45.957922+00	2026-03-04 14:17:44.809978+00	opt-6.7b GPTQ 4bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	fq8qxpxc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/fq8qxpxc	llm-quant-lab	\N	\N	\N	\N
2243	551c5883-70c5-47a4-ae81-594bec044c1b	2026-03-03 22:35:03.661274+00	2026-03-03 23:03:11.428164+00	Mistral-7B-v0.1 FP16 baseline	\N	\N	\N	mistralai/Mistral-7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	nsvbpfpu	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nsvbpfpu	llm-quant-lab	\N	\N	\N	\N
2244	17204d6e-2597-448e-b4f2-0e0599cf2d02	2026-03-03 22:35:03.663473+00	2026-03-03 23:06:38.479769+00	Mixtral-8x7B-v0.1 FP16 baseline	\N	\N	\N	mistralai/Mixtral-8x7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	lc5n3kgs	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/lc5n3kgs	llm-quant-lab	\N	\N	\N	\N
2248	832db999-ac1d-4a75-bbf3-228793ab3384	2026-03-03 22:35:03.672631+00	2026-03-03 23:09:38.061179+00	llama-7b FP16 baseline	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	2b029miv	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/2b029miv	llm-quant-lab	\N	\N	\N	\N
2249	b805fd29-f2fd-452f-8867-631b0fb922f6	2026-03-03 22:35:03.674857+00	2026-03-03 23:11:08.163083+00	llama-13b FP16 baseline	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	iblv7r7d	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/iblv7r7d	llm-quant-lab	\N	\N	\N	\N
2250	e241ea4d-1f75-498a-bdea-c60ec21ce13d	2026-03-03 22:35:03.677397+00	2026-03-03 23:13:47.75738+00	llama-30b FP16 baseline	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	9p0sks45	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9p0sks45	llm-quant-lab	\N	\N	\N	\N
2251	a5c51892-b3a9-44ac-a1bc-5611adb678cd	2026-03-03 22:35:03.679691+00	2026-03-03 23:19:14.020705+00	llama-65b FP16 baseline	\N	\N	\N	huggyllama/llama-65b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	rpo928ma	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/rpo928ma	llm-quant-lab	\N	\N	\N	\N
2252	73b2883a-9b41-4f83-a722-e9154dfe1134	2026-03-03 22:35:03.682006+00	2026-03-03 23:22:37.603258+00	Mixtral-8x7B-Instruct-v0.1 FP16 baseline	\N	\N	\N	mistralai/Mixtral-8x7B-Instruct-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	cqfuc8wz	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/cqfuc8wz	llm-quant-lab	\N	\N	\N	\N
2253	285b7f19-a8e0-4965-9a8a-d7b0dcecf66b	2026-03-03 22:35:03.684263+00	2026-03-03 23:23:47.964828+00	Mistral-7B-Instruct-v0.2 FP16 baseline	\N	\N	\N	mistralai/Mistral-7B-Instruct-v0.2	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	wdjj10c4	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/wdjj10c4	llm-quant-lab	\N	\N	\N	\N
2254	2968cfb9-21e8-4dae-ad70-170a4d1e2be2	2026-03-03 22:35:03.686494+00	2026-03-03 23:24:12.932721+00	opt-125m FP16 baseline	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	5knlt94x	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5knlt94x	llm-quant-lab	\N	\N	\N	\N
2256	19b99812-719b-4e2d-ac8a-4d7fb3cca747	2026-03-03 22:35:03.690933+00	2026-03-03 23:25:42.973277+00	opt-2.7b FP16 baseline	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	gfip8pjc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/gfip8pjc	llm-quant-lab	\N	\N	\N	\N
2257	67743e9c-f907-4756-a446-210f8bbab827	2026-03-03 22:35:03.693103+00	2026-03-03 23:26:36.16537+00	opt-6.7b FP16 baseline	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	oigbyq2l	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/oigbyq2l	llm-quant-lab	\N	\N	\N	\N
2261	870afb97-0483-4937-8785-2971d0f69db4	2026-03-03 22:35:03.702106+00	2026-03-03 23:29:02.166318+00	Llama-3.1-8B FP16 baseline	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	completed	\N	\N	{paper:paretoq,baseline,fp16}	b5jcrlm9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/b5jcrlm9	llm-quant-lab	\N	\N	\N	\N
2245	fee05c6f-a350-43b3-a27d-9107736408dd	2026-03-03 22:35:03.665881+00	2026-03-04 00:16:38.491022+00	Llama-2-7b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	5490kpbi	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5490kpbi	llm-quant-lab	\N	\N	\N	\N
2246	9dceea5e-32c6-444d-86ae-1035aca70aff	2026-03-03 22:35:03.6682+00	2026-03-04 00:39:54.559908+00	Llama-2-13b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	ffn4qklu	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ffn4qklu	llm-quant-lab	\N	\N	\N	\N
2212	ab4d0bf9-aeb2-4965-a26a-a2a1c074cca2	2026-03-03 22:34:54.535215+00	2026-03-04 03:18:03.504636+00	Llama-2-13b-hf AWQ 4bit retry	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	itzm13t6	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/itzm13t6	llm-quant-lab	\N	\N	\N	\N
2214	49e51644-8927-43b8-a660-c16b747b69fd	2026-03-03 22:34:54.550988+00	2026-03-04 03:54:15.702098+00	llama-30b AWQ 4bit retry	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	566x492i	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/566x492i	llm-quant-lab	\N	\N	\N	\N
2211	1a9d23a0-5ba8-4b3a-91e5-ef19d9d120d8	2026-03-03 22:34:54.527305+00	2026-03-03 22:38:17.092076+00	Llama-2-70b-hf SMOOTHQUANT 8bit retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 112.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 0 bytes is free. Of the allocated memory 148.14 GiB is allocated by PyTorch, and 779.48 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{reproduce-all,retry}	5o0f5fpp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5o0f5fpp	llm-quant-lab	\N	\N	\N	\N
2209	f5377403-bcc3-4b72-999c-8f89e034e7e8	2026-03-03 22:34:54.510813+00	2026-03-03 22:39:41.501716+00	bloom GPTQ 4bit retry	\N	\N	\N	bigscience/bloom	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 1.15 GiB. GPU 0 has a total capacity of 191.98 GiB of which 674.00 MiB is free. Of the allocated memory 182.62 GiB is allocated by PyTorch, and 315.78 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{reproduce-all,retry}	m50thvnf	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m50thvnf	llm-quant-lab	\N	\N	\N	\N
2223	ac65bec6-c6ab-4ffc-a576-24f7389813a8	2026-03-03 22:35:03.616346+00	2026-03-03 22:42:45.862395+00	opt-6.7b FP16 baseline	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	ifcea0f8	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ifcea0f8	llm-quant-lab	\N	\N	\N	\N
2218	8e8fa94f-ca65-40e1-934e-99166b6ca33b	2026-03-03 22:34:54.583661+00	2026-03-03 22:54:32.137038+00	Llama-3.1-8B GPTQ 2bit retry	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	5051ke6p	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5051ke6p	llm-quant-lab	\N	\N	\N	\N
2210	74ad9a5d-f157-4ccb-bb68-25a4156fe53d	2026-03-03 22:34:54.519229+00	2026-03-03 22:55:19.133993+00	Llama-2-13b-hf SMOOTHQUANT 8bit retry	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry}	lwlzi382	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/lwlzi382	llm-quant-lab	\N	\N	\N	\N
2237	a1e5a1de-7642-479b-a859-5f93bc852374	2026-03-03 22:35:03.647931+00	2026-03-03 22:58:45.357327+00	llama-13b FP16 baseline	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	g2rskbmw	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/g2rskbmw	llm-quant-lab	\N	\N	\N	\N
2247	f509f46d-41af-46fc-a440-1f58d5ef04b7	2026-03-03 22:35:03.670436+00	2026-03-03 23:08:29.329877+00	Llama-2-70b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 448.00 MiB. GPU 0 has a total capacity of 191.98 GiB of which 184.00 MiB is free. Of the allocated memory 68.79 GiB is allocated by PyTorch, and 38.67 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:awq,baseline,fp16}	767mq9t7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/767mq9t7	llm-quant-lab	\N	\N	\N	\N
2259	5a954528-f61f-452d-b499-97691b4c0b60	2026-03-03 22:35:03.697613+00	2026-03-03 23:28:04.3191+00	gpt-j-6b FP16 baseline	\N	\N	\N	EleutherAI/gpt-j-6b	\N	fp16	\N	\N	1	failed	Unknown model architecture for 'EleutherAI/gpt-j-6b'. Add it to LLMC_MODEL_TYPES or ARCHITECTURE_TO_LLMC. Supported: ['bloom', 'chatglm', 'codellama', 'cohere', 'deepseek', 'deepseek-v2', 'deepseek-v3', 'deepseekv2', 'deepseekv3', 'falcon', 'gemma', 'gemma2', 'glm4v', 'internlm', 'internomni', 'internvl2', 'internvl3', 'llama', 'llava', 'llava-next', 'llava-onevision', 'llavahf', 'minicpm', 'minicpmv', 'mistral', 'mixtral', 'mllama', 'opt', 'phi', 'phi-3', 'phi3', 'qwen', 'qwen2', 'qwen2.5-vl', 'qwen2.5vl', 'qwen2audio', 'qwen2moe', 'qwen2vl', 'qwen3', 'qwen3moe', 'smollm', 'stablelm', 'starcoder', 'tinyllama', 'videollava', 'vila']	\N	{paper:zeroquant,baseline,fp16}	\N	\N	\N	\N	\N	\N	\N
2260	18ab9c3a-595c-4a22-852a-343a77f3064f	2026-03-03 22:35:03.699858+00	2026-03-03 23:28:10.23431+00	gpt-neox-20b FP16 baseline	\N	\N	\N	EleutherAI/gpt-neox-20b	\N	fp16	\N	\N	1	failed	Unknown model architecture for 'EleutherAI/gpt-neox-20b'. Add it to LLMC_MODEL_TYPES or ARCHITECTURE_TO_LLMC. Supported: ['bloom', 'chatglm', 'codellama', 'cohere', 'deepseek', 'deepseek-v2', 'deepseek-v3', 'deepseekv2', 'deepseekv3', 'falcon', 'gemma', 'gemma2', 'glm4v', 'internlm', 'internomni', 'internvl2', 'internvl3', 'llama', 'llava', 'llava-next', 'llava-onevision', 'llavahf', 'minicpm', 'minicpmv', 'mistral', 'mixtral', 'mllama', 'opt', 'phi', 'phi-3', 'phi3', 'qwen', 'qwen2', 'qwen2.5-vl', 'qwen2.5vl', 'qwen2audio', 'qwen2moe', 'qwen2vl', 'qwen3', 'qwen3moe', 'smollm', 'stablelm', 'starcoder', 'tinyllama', 'videollava', 'vila']	\N	{paper:zeroquant,baseline,fp16}	\N	\N	\N	\N	\N	\N	\N
2546	744fb600-4876-4fb0-a87f-996ce79189fc	2026-03-04 08:59:45.997202+00	2026-03-04 15:01:49.071774+00	opt-6.7b RTN 4bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	fg3daz66	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/fg3daz66	llm-quant-lab	\N	\N	\N	\N
2266	a2f2e195-bfcd-4e04-9359-5283f99be910	2026-03-04 07:06:59.638006+00	2026-03-04 07:06:59.638006+00	Llama-3.1-8B GPTQ 2bit retry2	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	pending	\N	\N	{reproduce-all,retry2}	\N	\N	\N	\N	\N	\N	\N
2267	a27c5f5e-d2a3-4eb6-9b26-a9bcb25d47a4	2026-03-04 07:06:59.645422+00	2026-03-04 07:06:59.645422+00	Llama-2-13b-hf AWQ 3bit retry2	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	pending	\N	\N	{reproduce-all,retry2}	\N	\N	\N	\N	\N	\N	\N
2263	b24ad9fb-218f-4cad-a88d-b93a4ec5e89c	2026-03-04 07:06:59.615588+00	2026-03-04 07:18:27.821275+00	Llama-2-13b-hf SMOOTHQUANT 8bit retry2	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{reproduce-all,retry2}	9hysu0y5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/9hysu0y5	llm-quant-lab	\N	\N	\N	\N
2482	e982d727-ed86-4430-8801-32a4b84dca95	2026-03-04 08:59:45.651302+00	2026-03-04 09:00:17.785368+00	opt-125m FP16 baseline	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	2czl9cp7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/2czl9cp7	llm-quant-lab	\N	\N	\N	\N
2495	3513fb8b-a2d6-4c11-8905-5e82931284d7	2026-03-04 08:59:45.823702+00	2026-03-04 09:06:32.903863+00	bloom-7b1 FP16 baseline	\N	\N	\N	bigscience/bloom-7b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	iylqxqbt	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/iylqxqbt	llm-quant-lab	\N	\N	\N	\N
2264	ad1730e5-b127-48e2-b802-b479f55e474b	2026-03-04 07:06:59.62329+00	2026-03-04 08:33:14.821908+00	Llama-2-13b-hf AWQ 4bit retry2	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	failed	Experiment orphaned (container restarted while running)	\N	{reproduce-all,retry2}	pgnskep9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/pgnskep9	llm-quant-lab	\N	\N	\N	\N
2265	baf3494a-fd5d-4c51-974b-dbd06053bde5	2026-03-04 07:06:59.630786+00	2026-03-04 08:33:14.821908+00	llama-30b AWQ 4bit retry2	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	failed	Experiment orphaned (container restarted while running)	\N	{reproduce-all,retry2}	5yksklhp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5yksklhp	llm-quant-lab	\N	\N	\N	\N
2483	a323967a-da76-4652-aa78-6329332b9071	2026-03-04 08:59:45.663309+00	2026-03-04 09:00:31.277517+00	opt-350m FP16 baseline	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	llf6obw2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/llf6obw2	llm-quant-lab	\N	\N	\N	\N
2487	ad2bc6ad-2cfd-4084-937e-339c68776083	2026-03-04 08:59:45.676142+00	2026-03-04 09:02:19.785918+00	opt-13b FP16 baseline	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	97b42lv3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/97b42lv3	llm-quant-lab	\N	\N	\N	\N
2508	d2413713-61b0-4abc-b394-be83a39fa271	2026-03-04 08:59:45.854153+00	2026-03-04 10:44:02.123483+00	Llama-2-7b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	5fekupna	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5fekupna	llm-quant-lab	\N	\N	\N	\N
2521	652b510b-3deb-4cf3-8340-1e79aa95244c	2026-03-04 08:59:45.884413+00	2026-03-04 12:45:11.345089+00	opt-13b FP16 baseline	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	idqiplpa	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/idqiplpa	llm-quant-lab	\N	\N	\N	\N
2530	f4646609-2248-40a4-9f20-b2b8f26332ea	2026-03-04 08:59:45.960247+00	2026-03-04 14:35:07.169179+00	opt-13b GPTQ 4bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	ofo3txhq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ofo3txhq	llm-quant-lab	\N	\N	\N	\N
2511	6a1d0ead-07fa-49ab-ab73-88124648424c	2026-03-04 08:59:45.861015+00	2026-03-04 11:54:20.037411+00	llama-7b FP16 baseline	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	jj4emwcy	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/jj4emwcy	llm-quant-lab	\N	\N	\N	\N
2513	e08026f5-1d5e-44d4-8ea9-950a6806bf1b	2026-03-04 08:59:45.865856+00	2026-03-04 15:31:12.589204+00	llama-30b FP16 baseline	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	ns8qeksb	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ns8qeksb	llm-quant-lab	\N	\N	\N	\N
2512	cab9ca2b-5016-40af-9e60-aec8a47baaaf	2026-03-04 08:59:45.863507+00	2026-03-04 12:38:56.072369+00	llama-13b FP16 baseline	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	eobi21p0	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/eobi21p0	llm-quant-lab	\N	\N	\N	\N
2484	bb7bf65e-b4f6-4392-a0c9-423817bb94b0	2026-03-04 08:59:45.666662+00	2026-03-04 09:00:41.2887+00	opt-1.3b FP16 baseline	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	fsyoca41	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/fsyoca41	llm-quant-lab	\N	\N	\N	\N
2509	bc9e864c-4ec9-40cf-adf6-4dbb079a8938	2026-03-04 08:59:45.856398+00	2026-03-04 12:40:21.860872+00	Llama-2-13b-hf FP16 baseline	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	k7fdbn18	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/k7fdbn18	llm-quant-lab	\N	\N	\N	\N
2485	e47d3dcb-2aa3-4695-9e8f-e76c017a0ea6	2026-03-04 08:59:45.670417+00	2026-03-04 09:01:26.592803+00	opt-2.7b FP16 baseline	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	rfjmlw22	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/rfjmlw22	llm-quant-lab	\N	\N	\N	\N
2517	9ad92a3f-6af4-47a2-bfe4-d904b9a0c2e6	2026-03-04 08:59:45.875176+00	2026-03-04 12:41:27.463041+00	opt-125m FP16 baseline	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	dtyhmq90	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/dtyhmq90	llm-quant-lab	\N	\N	\N	\N
2518	11edcfd6-88fd-46f8-a7f2-3c768832530d	2026-03-04 08:59:45.877476+00	2026-03-04 12:42:02.10871+00	opt-1.3b FP16 baseline	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	quut41aq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/quut41aq	llm-quant-lab	\N	\N	\N	\N
2519	2169941e-c478-48da-a1c5-c802580e30b2	2026-03-04 08:59:45.879814+00	2026-03-04 12:42:46.928047+00	opt-2.7b FP16 baseline	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	1e3mph98	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/1e3mph98	llm-quant-lab	\N	\N	\N	\N
2520	9df6d61e-676e-40a0-ab15-d6de70b6e5bd	2026-03-04 08:59:45.882105+00	2026-03-04 12:43:46.453332+00	opt-6.7b FP16 baseline	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,baseline,fp16}	ic4ax4az	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ic4ax4az	llm-quant-lab	\N	\N	\N	\N
2516	2e570665-ce35-4c69-ab27-a907ff62d112	2026-03-04 08:59:45.872835+00	2026-03-04 13:57:41.922329+00	Mistral-7B-Instruct-v0.2 FP16 baseline	\N	\N	\N	mistralai/Mistral-7B-Instruct-v0.2	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16}	qzijk4hp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/qzijk4hp	llm-quant-lab	\N	\N	\N	\N
2486	e5c2fc0c-5be6-40b4-9f59-982ea28207d5	2026-03-04 08:59:45.673551+00	2026-03-04 09:02:03.555602+00	opt-6.7b FP16 baseline	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	65jesbl5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/65jesbl5	llm-quant-lab	\N	\N	\N	\N
2491	af535ed2-ebf9-4247-b01f-38fdefe20cd2	2026-03-04 08:59:45.814191+00	2026-03-04 09:03:46.747747+00	bloom-560m FP16 baseline	\N	\N	\N	bigscience/bloom-560m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	mshijxok	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mshijxok	llm-quant-lab	\N	\N	\N	\N
2492	c5d665b3-dec3-4bd0-82d1-52d61c7ee076	2026-03-04 08:59:45.816582+00	2026-03-04 09:04:06.451526+00	bloom-1b1 FP16 baseline	\N	\N	\N	bigscience/bloom-1b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	u28ko5yi	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/u28ko5yi	llm-quant-lab	\N	\N	\N	\N
2493	71db911f-e78c-443c-9961-23eb436326e8	2026-03-04 08:59:45.818968+00	2026-03-04 09:05:11.313536+00	bloom-1b7 FP16 baseline	\N	\N	\N	bigscience/bloom-1b7	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	4kx76g3r	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/4kx76g3r	llm-quant-lab	\N	\N	\N	\N
2488	34ad9eb4-0a9f-48f4-8ecf-8023e9e8e0e8	2026-03-04 08:59:45.678828+00	2026-03-04 09:05:40.181877+00	opt-30b FP16 baseline	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	akwmhobt	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/akwmhobt	llm-quant-lab	\N	\N	\N	\N
2494	c7792c76-791c-434b-a89f-d05ba37b1a88	2026-03-04 08:59:45.821362+00	2026-03-04 09:05:50.264754+00	bloom-3b FP16 baseline	\N	\N	\N	bigscience/bloom-3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16}	hgmafww9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hgmafww9	llm-quant-lab	\N	\N	\N	\N
2506	d2f8c148-7eff-4f7e-97c8-d87928cecd3d	2026-03-04 08:59:45.849587+00	2026-03-04 09:31:58.029555+00	Mistral-7B-v0.1 FP16 baseline	\N	\N	\N	mistralai/Mistral-7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	v1tsox3g	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/v1tsox3g	llm-quant-lab	\N	\N	\N	\N
2499	888c53b5-6aef-4d7b-82e8-52b28c08ce61	2026-03-04 08:59:45.833098+00	2026-03-04 09:40:32.815212+00	llama-7b FP16 baseline	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	nqaf3ac6	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nqaf3ac6	llm-quant-lab	\N	\N	\N	\N
2507	2c13f57b-9631-4298-a9cf-30ac4d24f553	2026-03-04 08:59:45.851871+00	2026-03-04 10:43:01.398928+00	Mixtral-8x7B-v0.1 FP16 baseline	\N	\N	\N	mistralai/Mixtral-8x7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16}	njbq8719	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/njbq8719	llm-quant-lab	\N	\N	\N	\N
2542	7a723d5d-fc78-48b6-906c-790ff21f16c3	2026-03-04 08:59:45.987946+00	2026-03-04 14:56:30.240217+00	opt-125m RTN 4bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	6kepf74n	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/6kepf74n	llm-quant-lab	\N	\N	\N	\N
2543	31bb23cc-caab-4747-a247-eab9e7b34c64	2026-03-04 08:59:45.990359+00	2026-03-04 14:57:38.88795+00	opt-350m RTN 4bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	fdcq3kve	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/fdcq3kve	llm-quant-lab	\N	\N	\N	\N
2544	ae4f29f6-cb1a-40f1-96b0-f8ba7efaf110	2026-03-04 08:59:45.992621+00	2026-03-04 14:58:42.659496+00	opt-1.3b RTN 4bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	3z6bhjcy	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/3z6bhjcy	llm-quant-lab	\N	\N	\N	\N
2545	cc8198d5-497c-4544-90a3-34c410de1638	2026-03-04 08:59:45.994937+00	2026-03-04 15:00:01.968172+00	opt-2.7b RTN 4bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	takwm8g1	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/takwm8g1	llm-quant-lab	\N	\N	\N	\N
2547	24506d88-9bca-4e03-911c-9918f4863e5d	2026-03-04 08:59:45.999454+00	2026-03-04 15:04:32.852902+00	opt-13b RTN 4bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	lbh052su	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/lbh052su	llm-quant-lab	\N	\N	\N	\N
2550	c4b1c4d9-403b-4953-93d4-cf2fced11a56	2026-03-04 08:59:46.006409+00	2026-03-04 15:10:26.392083+00	bloom-560m GPTQ 4bit	\N	\N	\N	bigscience/bloom-560m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	b2m3i2sj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/b2m3i2sj	llm-quant-lab	\N	\N	\N	\N
2539	bdb134ad-18f3-4aa2-9bb2-ae3a7cc0232c	2026-03-04 08:59:45.981017+00	2026-03-04 15:11:25.026892+00	opt-13b GPTQ 3bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	qm7snuf7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/qm7snuf7	llm-quant-lab	\N	\N	\N	\N
2524	887a41f7-4c86-4b1d-9011-343cca5d2bd2	2026-03-04 08:59:45.891447+00	2026-03-04 13:38:46.305329+00	Llama-3.1-8B FP16 baseline	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	completed	\N	\N	{paper:paretoq,baseline,fp16}	ifkzb4sn	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ifkzb4sn	llm-quant-lab	\N	\N	\N	\N
2551	8f8ebdbd-a416-486d-ad8e-164e48e0680b	2026-03-04 08:59:46.008738+00	2026-03-04 15:15:17.79469+00	bloom-1b1 GPTQ 4bit	\N	\N	\N	bigscience/bloom-1b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	7a87bjc9	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/7a87bjc9	llm-quant-lab	\N	\N	\N	\N
2525	e826895d-e55f-478e-9860-5fbd34c9adf4	2026-03-04 08:59:45.947167+00	2026-03-04 13:41:09.159866+00	opt-125m GPTQ 4bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	ii3e2k87	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ii3e2k87	llm-quant-lab	\N	\N	\N	\N
2526	7ded687a-3574-4ad0-bf49-0d7e35da9e99	2026-03-04 08:59:45.950478+00	2026-03-04 13:45:44.054691+00	opt-350m GPTQ 4bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	k8pow0zp	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/k8pow0zp	llm-quant-lab	\N	\N	\N	\N
2552	1a8988bb-842f-4df3-bce4-a68d7e3282bb	2026-03-04 08:59:46.011054+00	2026-03-04 15:18:00.894768+00	bloom-1b7 GPTQ 4bit	\N	\N	\N	bigscience/bloom-1b7	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	hkm5q7fx	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hkm5q7fx	llm-quant-lab	\N	\N	\N	\N
2553	a8551424-712f-4cc0-9482-4e249a4a3e43	2026-03-04 08:59:46.013351+00	2026-03-04 15:26:43.711388+00	bloom-3b GPTQ 4bit	\N	\N	\N	bigscience/bloom-3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	2vfojpqd	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/2vfojpqd	llm-quant-lab	\N	\N	\N	\N
2528	43382371-16a6-4e73-8270-d79559724a99	2026-03-04 08:59:45.955512+00	2026-03-04 14:06:27.927283+00	opt-2.7b GPTQ 4bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	ktuv1uvh	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ktuv1uvh	llm-quant-lab	\N	\N	\N	\N
2534	440107c2-4c37-4617-b218-2467ee9fcebd	2026-03-04 08:59:45.969448+00	2026-03-04 14:21:58.774276+00	opt-125m GPTQ 3bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	volfw6na	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/volfw6na	llm-quant-lab	\N	\N	\N	\N
2535	6f39230d-02d4-4568-ab1e-6357405dd62d	2026-03-04 08:59:45.971729+00	2026-03-04 14:26:59.180579+00	opt-350m GPTQ 3bit	\N	\N	\N	facebook/opt-350m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	hn5dj2kl	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/hn5dj2kl	llm-quant-lab	\N	\N	\N	\N
2536	841341c3-b81d-4043-a8e7-e580f51ede4d	2026-03-04 08:59:45.974054+00	2026-03-04 14:34:32.78029+00	opt-1.3b GPTQ 3bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	mj65z913	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mj65z913	llm-quant-lab	\N	\N	\N	\N
2561	1397a4e2-46dc-4762-8c6d-b616d75c28be	2026-03-04 08:59:46.032007+00	2026-03-04 16:17:21.758775+00	llama-13b SMOOTHQUANT 8bit	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	mvu664kt	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mvu664kt	llm-quant-lab	\N	\N	\N	\N
2537	5ac7c22d-a956-4fae-b08c-7d575f10b77e	2026-03-04 08:59:45.976414+00	2026-03-04 14:47:46.731478+00	opt-2.7b GPTQ 3bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	owy7p20n	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/owy7p20n	llm-quant-lab	\N	\N	\N	\N
2538	48a7a2e4-88ea-4161-8135-0b5649c742b6	2026-03-04 08:59:45.978704+00	2026-03-04 14:54:25.817161+00	opt-6.7b GPTQ 3bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all}	7qphjusc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/7qphjusc	llm-quant-lab	\N	\N	\N	\N
2570	92daa1b0-1a71-4687-9fc9-cc630fe1a309	2026-03-04 08:59:46.053394+00	2026-03-04 19:43:26.274935+00	Llama-2-7b-hf GPTQ 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	a0sgb93o	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/a0sgb93o	llm-quant-lab	\N	\N	\N	\N
2569	5179ac0e-9c9b-46ea-8528-69d752011240	2026-03-04 08:59:46.050994+00	2026-03-04 20:45:21.943485+00	Llama-2-7b-hf AWQ 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	b2xsmv02	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/b2xsmv02	llm-quant-lab	\N	\N	\N	\N
2574	32640dcb-808f-409c-a9f6-78acb8c5c05e	2026-03-04 08:59:46.062897+00	2026-03-04 23:28:21.72494+00	llama-7b AWQ 4bit	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	j0v66bln	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/j0v66bln	llm-quant-lab	\N	\N	\N	\N
2572	88516566-eb6b-4e33-9cb7-53438d4d2d3a	2026-03-04 08:59:46.058088+00	2026-03-05 00:44:03.736978+00	Llama-2-13b-hf AWQ 4bit	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	m590bc7l	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m590bc7l	llm-quant-lab	\N	\N	\N	\N
2575	3ff5a586-cb98-43f9-9628-8da9f22e546f	2026-03-04 08:59:46.065301+00	2026-03-05 01:27:46.492401+00	llama-13b AWQ 4bit	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	yofhf2vt	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/yofhf2vt	llm-quant-lab	\N	\N	\N	\N
2562	5f1fecb9-3b03-495d-a7a4-cc9bf7818055	2026-03-04 08:59:46.034385+00	2026-03-04 17:05:17.666994+00	Llama-2-7b-hf SMOOTHQUANT 8bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	3i2qwjfa	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/3i2qwjfa	llm-quant-lab	\N	\N	\N	\N
2563	072b5fdf-a2bf-4598-a20c-9fb687d0ea28	2026-03-04 08:59:46.036806+00	2026-03-04 17:12:35.406355+00	Llama-2-13b-hf SMOOTHQUANT 8bit	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	chpqvlsv	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/chpqvlsv	llm-quant-lab	\N	\N	\N	\N
2567	dfb1aaae-fbe8-4365-95b9-d80ea7e37d24	2026-03-04 08:59:46.046254+00	2026-03-04 17:18:38.491171+00	Mistral-7B-v0.1 SMOOTHQUANT 8bit	\N	\N	\N	mistralai/Mistral-7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all}	s4b60frv	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/s4b60frv	llm-quant-lab	\N	\N	\N	\N
2583	b4160578-8107-40ff-85f8-fed5f7e6b1c9	2026-03-04 08:59:46.085614+00	2026-03-05 02:08:51.348598+00	opt-125m LLMINT8 8bit	\N	\N	\N	facebook/opt-125m	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	khpakg8w	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/khpakg8w	llm-quant-lab	\N	\N	\N	\N
2571	71008848-1c06-41b7-83e0-e7a4b6f08c0a	2026-03-04 08:59:46.055737+00	2026-03-04 19:42:46.237979+00	Llama-2-7b-hf RTN 4bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	m5cf358g	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m5cf358g	llm-quant-lab	\N	\N	\N	\N
2584	a52ec764-797b-488d-a802-d147dff29667	2026-03-04 08:59:46.088016+00	2026-03-05 02:09:32.884879+00	opt-1.3b LLMINT8 8bit	\N	\N	\N	facebook/opt-1.3b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	xgpqspu5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/xgpqspu5	llm-quant-lab	\N	\N	\N	\N
2585	1a74133c-cedb-4fc8-a488-034a704c2674	2026-03-04 08:59:46.090556+00	2026-03-05 02:10:25.511602+00	opt-2.7b LLMINT8 8bit	\N	\N	\N	facebook/opt-2.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	apat34jo	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/apat34jo	llm-quant-lab	\N	\N	\N	\N
2586	898554ba-ec5a-4d46-a977-578f7db519ea	2026-03-04 08:59:46.093196+00	2026-03-05 02:11:33.328906+00	opt-6.7b LLMINT8 8bit	\N	\N	\N	facebook/opt-6.7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	83gtdido	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/83gtdido	llm-quant-lab	\N	\N	\N	\N
2587	8f4dbdf6-9a34-43ca-8bb3-cdb0aab9b6cb	2026-03-04 08:59:46.095653+00	2026-03-05 02:13:08.211909+00	opt-13b LLMINT8 8bit	\N	\N	\N	facebook/opt-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:llmint8,reproduce-all}	mv57m7q1	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mv57m7q1	llm-quant-lab	\N	\N	\N	\N
2588	bb839b5e-dab8-4e4e-b11a-152c1c9a612c	2026-03-04 08:59:46.098987+00	2026-03-05 02:28:31.87817+00	Llama-3.1-8B GPTQ 2bit	\N	\N	\N	meta-llama/Llama-3.1-8B	\N	fp16	\N	\N	1	completed	\N	\N	{paper:paretoq,reproduce-all}	okji0oaf	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/okji0oaf	llm-quant-lab	\N	\N	\N	\N
2578	c0437627-bd13-4110-acdc-32793a725f8c	2026-03-04 08:59:46.072709+00	2026-03-05 03:23:40.735363+00	Llama-2-7b-hf AWQ 3bit	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	m10qy10r	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/m10qy10r	llm-quant-lab	\N	\N	\N	\N
2581	893beda7-ddd6-4e4c-8070-f4f175167d1e	2026-03-04 08:59:46.080629+00	2026-03-05 04:50:17.787786+00	Mixtral-8x7B-Instruct-v0.1 AWQ 4bit	\N	\N	\N	mistralai/Mixtral-8x7B-Instruct-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all}	e2l9stix	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/e2l9stix	llm-quant-lab	\N	\N	\N	\N
2633	3698ff6d-6e8f-483e-b5d0-4987b64f145f	2026-03-05 08:40:18.235717+00	2026-03-05 09:17:13.965323+00	opt-iml-30b retry	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16,reproduce-all,retry}	1f13f0bk	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/1f13f0bk	llm-quant-lab	\N	\N	\N	\N
2634	e0883e3a-d32d-4b05-b06b-d1506a7e4a9a	2026-03-05 08:40:18.238184+00	2026-03-05 09:43:40.614403+00	llama-13b retry	\N	\N	\N	huggyllama/llama-13b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16,reproduce-all,retry}	ihy6le1m	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ihy6le1m	llm-quant-lab	\N	\N	\N	\N
2635	b3409a2b-9fa0-481a-ad8a-731930a1a650	2026-03-05 08:40:18.240541+00	2026-03-05 10:05:24.618865+00	Llama-2-7b-hf retry	\N	\N	\N	meta-llama/Llama-2-7b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16,reproduce-all,retry}	vzmliwp0	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/vzmliwp0	llm-quant-lab	\N	\N	\N	\N
2636	8cbc38ce-7167-4480-87d0-bf0fd464912d	2026-03-05 08:40:18.369158+00	2026-03-05 10:32:01.199631+00	Llama-2-13b-hf retry	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16,reproduce-all,retry}	qzsr7s7h	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/qzsr7s7h	llm-quant-lab	\N	\N	\N	\N
2637	d134c846-e105-4e03-b25d-00400f1ba4dc	2026-03-05 08:40:18.371752+00	2026-03-05 11:40:45.147036+00	Llama-2-70b-hf retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,baseline,fp16,reproduce-all,retry}	yky1axh2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/yky1axh2	llm-quant-lab	\N	\N	\N	\N
2640	f3e56ac5-0118-48a7-9a4f-abdc412517a5	2026-03-05 08:40:18.378974+00	2026-03-05 14:40:50.367856+00	Llama-2-70b-hf retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16,reproduce-all,retry}	h687kt3v	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/h687kt3v	llm-quant-lab	\N	\N	\N	\N
2642	30ab452c-8522-48d1-85db-860c0a4150c8	2026-03-05 08:40:18.383664+00	2026-03-05 19:31:08.401199+00	Mixtral-8x7B-Instruct-v0.1 retry	\N	\N	\N	mistralai/Mixtral-8x7B-Instruct-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16,reproduce-all,retry}	87ak2kl3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/87ak2kl3	llm-quant-lab	\N	\N	\N	\N
2645	a04f8f00-c1ee-472f-b1c0-65bc34c46135	2026-03-05 08:40:18.390479+00	2026-03-05 20:01:50.273925+00	opt-30b retry	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all,retry}	e9owf4s3	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/e9owf4s3	llm-quant-lab	\N	\N	\N	\N
2648	3db1495e-deba-417b-891b-931e6b3d71e3	2026-03-05 08:40:18.401867+00	2026-03-05 21:32:31.615656+00	opt-30b retry	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all,retry}	05tgsiuz	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/05tgsiuz	llm-quant-lab	\N	\N	\N	\N
2629	cab75b32-9891-45ef-9257-a29a6bda0e2e	2026-03-05 08:40:18.21783+00	2026-03-05 08:48:09.926727+00	opt-66b retry	\N	\N	\N	facebook/opt-66b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,baseline,fp16,reproduce-all,retry}	mnj4h0d2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/mnj4h0d2	llm-quant-lab	\N	\N	\N	\N
2641	ed02a115-0ac3-4839-9e64-7aee1e344940	2026-03-05 08:40:18.38129+00	2026-03-05 17:34:51.900054+00	llama-65b retry	\N	\N	\N	huggyllama/llama-65b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,baseline,fp16,reproduce-all,retry}	qbumlz89	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/qbumlz89	llm-quant-lab	\N	\N	\N	\N
2650	b9a6d440-bfe4-447a-8875-900aa128f130	2026-03-05 08:40:18.406518+00	2026-03-05 21:36:47.450021+00	opt-30b retry	\N	\N	\N	facebook/opt-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all,retry}	lih7q9x7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/lih7q9x7	llm-quant-lab	\N	\N	\N	\N
2646	e20b64ed-cfac-42e9-b8d8-b58975b22d1a	2026-03-05 08:40:18.392701+00	2026-03-05 21:01:36.322992+00	opt-66b retry	\N	\N	\N	facebook/opt-66b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all,retry}	4nwz47kg	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/4nwz47kg	llm-quant-lab	\N	\N	\N	\N
2652	60507b2f-0e56-4389-b42d-6d8038b16e1b	2026-03-05 08:40:18.410989+00	2026-03-05 21:47:16.249766+00	bloom-7b1 retry	\N	\N	\N	bigscience/bloom-7b1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:gptq,reproduce-all,retry}	c58zqndj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/c58zqndj	llm-quant-lab	\N	\N	\N	\N
2656	d3b80d24-8334-4863-88a4-3e0a538d32bb	2026-03-05 08:40:18.420071+00	2026-03-05 23:22:35.099974+00	opt-iml-30b retry	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all,retry}	l839gwk7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/l839gwk7	llm-quant-lab	\N	\N	\N	\N
2657	921f7608-c361-4add-a903-d263953a395a	2026-03-05 08:40:18.422304+00	2026-03-05 23:49:31.662819+00	opt-iml-30b retry	\N	\N	\N	facebook/opt-iml-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all,retry}	o70ko3x5	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/o70ko3x5	llm-quant-lab	\N	\N	\N	\N
2658	01a95b26-b838-4567-995f-e2ebd22c1b33	2026-03-05 08:40:18.424547+00	2026-03-06 00:37:09.452712+00	llama-7b retry	\N	\N	\N	huggyllama/llama-7b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all,retry}	0kljagtj	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/0kljagtj	llm-quant-lab	\N	\N	\N	\N
2662	c1fa5310-3a13-49d2-a6af-bbf0b7f0d337	2026-03-05 08:40:18.433658+00	2026-03-06 04:27:51.114059+00	Mixtral-8x7B-v0.1 retry	\N	\N	\N	mistralai/Mixtral-8x7B-v0.1	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,reproduce-all,retry}	nn9uoqhe	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/nn9uoqhe	llm-quant-lab	\N	\N	\N	\N
2664	cfe774d5-4d62-43c9-86be-db4b83808814	2026-03-05 08:40:18.438226+00	2026-03-06 11:51:26.718879+00	llama-30b retry	\N	\N	\N	huggyllama/llama-30b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all,retry}	pm9y2ows	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/pm9y2ows	llm-quant-lab	\N	\N	\N	\N
2665	c5775885-5cca-409b-b53c-95ef6ed49555	2026-03-05 08:40:18.440446+00	2026-03-06 19:11:42.873873+00	llama-65b retry	\N	\N	\N	huggyllama/llama-65b	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all,retry}	pv8mw8uc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/pv8mw8uc	llm-quant-lab	\N	\N	\N	\N
2666	7dec9075-4f2c-41fe-89e9-2a9f283cf857	2026-03-05 08:40:18.442661+00	2026-03-06 23:44:45.633356+00	Llama-2-13b-hf retry	\N	\N	\N	meta-llama/Llama-2-13b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all,retry}	ood1kgh7	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/ood1kgh7	llm-quant-lab	\N	\N	\N	\N
2668	0f502a57-2cce-47a8-af06-d874a20c5b6b	2026-03-05 08:40:18.447101+00	2026-03-07 02:58:18.736427+00	Mistral-7B-Instruct-v0.2 retry	\N	\N	\N	mistralai/Mistral-7B-Instruct-v0.2	\N	fp16	\N	\N	1	completed	\N	\N	{paper:awq,reproduce-all,retry}	msd6ygkq	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/msd6ygkq	llm-quant-lab	\N	\N	\N	\N
2685	974737e5-e748-4a3e-a0b9-ffcbc1dabe72	2026-03-08 08:52:15.225232+00	2026-03-08 09:00:05.844484+00	Llama-2-70b-hf retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	Experiment orphaned (container restarted while running)	\N	{paper:awq,retry,reproduce-all,retry}	otgz2adk	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/otgz2adk	llm-quant-lab	\N	\N	\N	\N
2686	04eff1e8-badd-4556-9179-1d523b94ab76	2026-03-08 08:52:15.227437+00	2026-03-08 09:00:05.844484+00	Llama-2-70b-hf retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	failed	Experiment orphaned (container restarted while running)	\N	{paper:awq,retry,reproduce-all,retry}	xkhogn61	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/xkhogn61	llm-quant-lab	\N	\N	\N	\N
2705	86f48229-7e9e-4815-bb08-ce347478d90a	2026-03-08 11:05:54.46033+00	2026-03-08 11:05:54.46033+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:smoothquant,baseline,fp16,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2710	7654fa7e-745e-4d5f-9ca1-0027beef5db4	2026-03-08 11:05:54.477464+00	2026-03-08 11:05:54.477464+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:gptq,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2711	954b4cc7-3f90-4821-a810-37afb5aef47c	2026-03-08 11:05:54.4808+00	2026-03-08 11:05:54.4808+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:gptq,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2712	6a9af20a-bd4b-46ea-88c9-1a8ef0e8e0f3	2026-03-08 11:05:54.483957+00	2026-03-08 11:05:54.483957+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:gptq,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2714	64d576b8-c734-4e5d-a14f-a0f485ab4f99	2026-03-08 11:05:54.490294+00	2026-03-08 11:05:54.490294+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:smoothquant,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2715	833453db-f467-4aae-b027-0a5d9e4e119c	2026-03-08 11:05:54.493499+00	2026-03-08 11:05:54.493499+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:smoothquant,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2718	1bffc4fb-13a4-4ddd-bb94-f9db27be9d96	2026-03-08 11:05:54.503183+00	2026-03-08 11:05:54.503183+00	falcon-40b retry	\N	\N	\N	tiiuae/falcon-40b	\N	fp16	\N	\N	1	pending	\N	\N	{paper:smoothquant,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2719	e4ce25df-8e1e-4ced-986b-d4f5c6233739	2026-03-08 11:07:26.19559+00	2026-03-08 11:07:37.352685+00	opt-175b retry	\N	\N	\N	facebook/opt-175b	\N	fp16	\N	\N	1	failed	facebook/opt-175b is not a local folder and is not a valid model identifier listed on 'https://huggingface.co/models'	\N	{paper:gptq,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	5w8048zr	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/5w8048zr	llm-quant-lab	\N	\N	\N	\N
2727	fb09f030-099e-44d6-9b2e-d5ca5bc40ea9	2026-03-08 11:07:26.348392+00	2026-03-08 11:08:03.338155+00	falcon-7b retry	\N	\N	\N	tiiuae/falcon-7b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,retry,retry,retry,retry,reproduce-all,retry}	kku9d6rs	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/kku9d6rs	llm-quant-lab	\N	\N	\N	\N
2724	3d225e87-0f6c-4c34-bc2d-1ce660724527	2026-03-08 11:07:26.213963+00	2026-03-08 11:08:09.369794+00	gpt-neox-20b retry	\N	\N	\N	EleutherAI/gpt-neox-20b	\N	fp16	\N	\N	1	failed	Unknown model architecture for 'EleutherAI/gpt-neox-20b'. Add it to LLMC_MODEL_TYPES or ARCHITECTURE_TO_LLMC. Supported: ['bloom', 'chatglm', 'codellama', 'cohere', 'deepseek', 'deepseek-v2', 'deepseek-v3', 'deepseekv2', 'deepseekv3', 'falcon', 'gemma', 'gemma2', 'glm4v', 'internlm', 'internomni', 'internvl2', 'internvl3', 'llama', 'llava', 'llava-next', 'llava-onevision', 'llavahf', 'minicpm', 'minicpmv', 'mistral', 'mixtral', 'mllama', 'opt', 'phi', 'phi-3', 'phi3', 'qwen', 'qwen2', 'qwen2.5-vl', 'qwen2.5vl', 'qwen2audio', 'qwen2moe', 'qwen2vl', 'qwen3', 'qwen3moe', 'smollm', 'stablelm', 'starcoder', 'tinyllama', 'videollava', 'vila']	\N	{paper:zeroquant,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
2720	291672be-cb86-468b-b8b4-82d9766a01c4	2026-03-08 11:07:26.205159+00	2026-03-08 11:09:27.785418+00	bloom retry	\N	\N	\N	bigscience/bloom	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 1.15 GiB. GPU 0 has a total capacity of 191.98 GiB of which 674.00 MiB is free. Of the allocated memory 182.62 GiB is allocated by PyTorch, and 315.75 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:gptq,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	xt6v5djz	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/xt6v5djz	llm-quant-lab	\N	\N	\N	\N
2721	886be4f8-6427-4e29-8a53-a657d927a941	2026-03-08 11:07:26.207523+00	2026-03-08 11:10:00.911964+00	falcon-7b retry	\N	\N	\N	tiiuae/falcon-7b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	91xwy0mc	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/91xwy0mc	llm-quant-lab	\N	\N	\N	\N
2725	4d3f2603-1609-494f-bdfe-6f905382342f	2026-03-08 11:07:26.216055+00	2026-03-08 11:10:37.306023+00	bloom retry	\N	\N	\N	bigscience/bloom	\N	fp16	\N	\N	1	failed	HIP out of memory. Tried to allocate 1.53 GiB. GPU 0 has a total capacity of 191.98 GiB of which 1.04 GiB is free. Of the allocated memory 189.89 GiB is allocated by PyTorch, and 395.23 MiB is reserved by PyTorch but unallocated. If reserved but unallocated memory is large try setting PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True to avoid fragmentation.  See documentation for Memory Management  (https://pytorch.org/docs/stable/notes/cuda.html#environment-variables)	\N	{paper:gptq,retry,retry,retry,retry,reproduce-all,retry}	d1jza6o2	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/d1jza6o2	llm-quant-lab	\N	\N	\N	\N
2726	15bc233a-918a-432f-b313-d81c97b4e360	2026-03-08 11:07:26.345967+00	2026-03-08 13:39:10.931444+00	Llama-2-70b-hf retry	\N	\N	\N	meta-llama/Llama-2-70b-hf	\N	fp16	\N	\N	1	completed	\N	\N	{paper:smoothquant,retry,retry,retry,retry,reproduce-all,retry}	1hkbx29k	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/1hkbx29k	llm-quant-lab	\N	\N	\N	\N
2722	46066ca7-110d-464a-b417-2dcd9a7354f8	2026-03-08 11:07:26.20972+00	2026-03-08 13:40:26.912459+00	falcon-40b retry	\N	\N	\N	tiiuae/falcon-40b	\N	fp16	\N	\N	1	failed	'FalconModel' object has no attribute 'rotary_emb'	\N	{paper:smoothquant,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	n1fs154d	https://wandb.ai/medhat-abouzeid-25/llm-quant-lab/runs/n1fs154d	llm-quant-lab	\N	\N	\N	\N
2723	7fac8400-5329-48b8-b11a-98d1a5e42dda	2026-03-08 11:07:26.211877+00	2026-03-08 11:10:06.783578+00	gpt-j-6b retry	\N	\N	\N	EleutherAI/gpt-j-6b	\N	fp16	\N	\N	1	failed	Unknown model architecture for 'EleutherAI/gpt-j-6b'. Add it to LLMC_MODEL_TYPES or ARCHITECTURE_TO_LLMC. Supported: ['bloom', 'chatglm', 'codellama', 'cohere', 'deepseek', 'deepseek-v2', 'deepseek-v3', 'deepseekv2', 'deepseekv3', 'falcon', 'gemma', 'gemma2', 'glm4v', 'internlm', 'internomni', 'internvl2', 'internvl3', 'llama', 'llava', 'llava-next', 'llava-onevision', 'llavahf', 'minicpm', 'minicpmv', 'mistral', 'mixtral', 'mllama', 'opt', 'phi', 'phi-3', 'phi3', 'qwen', 'qwen2', 'qwen2.5-vl', 'qwen2.5vl', 'qwen2audio', 'qwen2moe', 'qwen2vl', 'qwen3', 'qwen3moe', 'smollm', 'stablelm', 'starcoder', 'tinyllama', 'videollava', 'vila']	\N	{paper:zeroquant,baseline,fp16,retry,retry,retry,retry,reproduce-all,retry}	\N	\N	\N	\N	\N	\N	\N
\.


--
-- Data for Name: hardware_stats; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.hardware_stats (id, experiment_id, quant_config_id, created_at, gpu_type, gpu_memory_gb, latency_p50, latency_p95, latency_p99, latency_mean, latency_std, tokens_per_second, batch_size, sequence_length, memory_allocated, memory_reserved, memory_peak, power_avg, power_peak, energy_joules, model_size_mb, quantized_size_mb, compression_ratio, extra_metadata) FROM stdin;
\.


--
-- Data for Name: knowledge_edges; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.knowledge_edges (id, source_id, target_id, edge_type, strength, metadata_json, created_at) FROM stdin;
1	algo_gptq	sch_w4	implements	1	{}	2026-02-25 13:45:38.299947+00
2	algo_gptq	sch_w4_g128	implements	0.9	{}	2026-02-25 13:45:38.299947+00
3	algo_gptq	sch_w3	implements	0.8	{}	2026-02-25 13:45:38.299947+00
4	algo_gptq	sch_w2	implements	0.6	{}	2026-02-25 13:45:38.299947+00
5	algo_awq	sch_w4	implements	1	{}	2026-02-25 13:45:38.299947+00
6	algo_awq	sch_w4_g128	implements	0.9	{}	2026-02-25 13:45:38.299947+00
7	algo_awq	sch_w3	implements	0.7	{}	2026-02-25 13:45:38.299947+00
8	algo_smoothquant	sch_stat_a8w8	implements	1	{}	2026-02-25 13:45:38.299947+00
9	algo_smoothquant	sch_dyn_a8w8	implements	0.9	{}	2026-02-25 13:45:38.299947+00
10	algo_hqq	sch_w4	implements	1	{}	2026-02-25 13:45:38.299947+00
11	algo_hqq	sch_w2	implements	0.7	{}	2026-02-25 13:45:38.299947+00
12	algo_hqq	sch_w3	implements	0.8	{}	2026-02-25 13:45:38.299947+00
13	algo_rtn	sch_w4	implements	0.8	{}	2026-02-25 13:45:38.299947+00
14	algo_rtn	sch_a16w8	implements	0.9	{}	2026-02-25 13:45:38.299947+00
15	algo_quarot	sch_dyn_a4w4	implements	1	{}	2026-02-25 13:45:38.299947+00
16	algo_quarot	sch_dyn_a8w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
17	algo_llmint8	sch_dyn_a8w8	implements	1	{}	2026-02-25 13:45:38.299947+00
18	algo_zeroquant	sch_dyn_a8w8	implements	1	{}	2026-02-25 13:45:38.299947+00
19	algo_zeroquant	sch_stat_a8w8	implements	0.8	{}	2026-02-25 13:45:38.299947+00
20	algo_bitnet	sch_w2	implements	0.5	{}	2026-02-25 13:45:38.299947+00
21	algo_paretoq	sch_w2	implements	1	{"note": "QAT 2-bit via Stretched Elastic Quant (SEQ)"}	2026-02-25 13:45:38.299947+00
22	algo_paretoq	sch_w3	implements	1	{}	2026-02-25 13:45:38.299947+00
23	algo_paretoq	sch_w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
24	algo_omniquant	sch_w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
25	algo_omniquant	sch_dyn_a8w4	implements	0.8	{}	2026-02-25 13:45:38.299947+00
26	algo_spqr	sch_w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
27	algo_spqr	sch_w3	implements	0.8	{}	2026-02-25 13:45:38.299947+00
28	algo_owq	sch_w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
29	algo_qlora	sch_qlora	implements	1	{}	2026-02-25 13:45:38.299947+00
30	algo_qlora	sch_w4	implements	0.7	{}	2026-02-25 13:45:38.299947+00
31	algo_fp8quant	sch_fp8_a8w8	implements	1	{}	2026-02-25 13:45:38.299947+00
32	algo_fp8quant	sch_fp8_kvcache	implements	0.8	{}	2026-02-25 13:45:38.299947+00
33	algo_kvcache_quant	sch_fp8_kvcache	implements	1	{}	2026-02-25 13:45:38.299947+00
34	algo_atom	sch_dyn_a4w4	implements	1	{}	2026-02-25 13:45:38.299947+00
35	algo_atom	sch_dyn_a8w4	implements	0.8	{}	2026-02-25 13:45:38.299947+00
36	algo_quik	sch_dyn_a4w4	implements	1	{}	2026-02-25 13:45:38.299947+00
37	algo_quik	sch_dyn_a8w4	implements	0.7	{}	2026-02-25 13:45:38.299947+00
38	algo_squeezellm	sch_w4	implements	0.9	{}	2026-02-25 13:45:38.299947+00
39	algo_squeezellm	sch_w3	implements	0.8	{}	2026-02-25 13:45:38.299947+00
40	algo_qat_generic	sch_dyn_a8w8	implements	0.7	{}	2026-02-25 13:45:38.299947+00
41	algo_qat_generic	sch_w4	implements	0.7	{}	2026-02-25 13:45:38.299947+00
42	algo_gptq	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
43	algo_gptq	dt_int3	uses	0.8	{}	2026-02-25 13:45:38.299947+00
44	algo_gptq	dt_int2	uses	0.5	{}	2026-02-25 13:45:38.299947+00
45	algo_gptq	dt_int8	uses	0.7	{}	2026-02-25 13:45:38.299947+00
46	algo_awq	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
47	algo_awq	dt_int3	uses	0.6	{}	2026-02-25 13:45:38.299947+00
48	algo_smoothquant	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
49	algo_hqq	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
50	algo_hqq	dt_int2	uses	0.7	{}	2026-02-25 13:45:38.299947+00
51	algo_hqq	dt_int3	uses	0.8	{}	2026-02-25 13:45:38.299947+00
52	algo_rtn	dt_int4	uses	0.9	{}	2026-02-25 13:45:38.299947+00
53	algo_rtn	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
54	algo_quarot	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
55	algo_llmint8	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
56	algo_zeroquant	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
57	algo_zeroquant	dt_int4	uses	0.6	{}	2026-02-25 13:45:38.299947+00
58	algo_bitnet	dt_ternary	uses	1	{}	2026-02-25 13:45:38.299947+00
59	algo_bitnet	dt_binary	uses	0.8	{}	2026-02-25 13:45:38.299947+00
60	algo_paretoq	dt_binary	uses	0.7	{"note": "1-bit binary quantization"}	2026-02-25 13:45:38.299947+00
61	algo_paretoq	dt_ternary	uses	1	{"note": "1.58-bit ternary via SEQ; best size-accuracy tradeoff per paper"}	2026-02-25 13:45:38.299947+00
62	algo_paretoq	dt_int2	uses	1	{}	2026-02-25 13:45:38.299947+00
63	algo_paretoq	dt_int3	uses	0.9	{}	2026-02-25 13:45:38.299947+00
64	algo_paretoq	dt_int4	uses	0.8	{}	2026-02-25 13:45:38.299947+00
65	algo_omniquant	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
66	algo_omniquant	dt_int8	uses	0.7	{}	2026-02-25 13:45:38.299947+00
67	algo_spqr	dt_int4	uses	0.9	{}	2026-02-25 13:45:38.299947+00
68	algo_spqr	dt_int3	uses	0.8	{}	2026-02-25 13:45:38.299947+00
69	algo_owq	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
70	algo_qlora	dt_nf4	uses	1	{}	2026-02-25 13:45:38.299947+00
71	algo_qlora	dt_fp16	uses	0.8	{}	2026-02-25 13:45:38.299947+00
72	algo_fp8quant	dt_fp8_e4m3	uses	1	{}	2026-02-25 13:45:38.299947+00
73	algo_fp8quant	dt_fp8_e5m2	uses	0.9	{}	2026-02-25 13:45:38.299947+00
74	algo_fp8quant	dt_fp8_e4m3fn	uses	0.8	{}	2026-02-25 13:45:38.299947+00
75	algo_kvcache_quant	dt_fp8_e4m3	uses	1	{}	2026-02-25 13:45:38.299947+00
76	algo_kvcache_quant	dt_int8	uses	0.8	{}	2026-02-25 13:45:38.299947+00
77	algo_atom	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
78	algo_quik	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
79	algo_quik	dt_fp16	uses	0.6	{"note": "outlier columns kept in FP16"}	2026-02-25 13:45:38.299947+00
80	algo_squeezellm	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
81	algo_squeezellm	dt_int3	uses	0.8	{}	2026-02-25 13:45:38.299947+00
82	algo_qat_generic	dt_int8	uses	0.8	{}	2026-02-25 13:45:38.299947+00
83	algo_qat_generic	dt_int4	uses	0.7	{}	2026-02-25 13:45:38.299947+00
84	sch_w4	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
85	sch_w4_g128	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
86	sch_w3	dt_int3	uses	1	{}	2026-02-25 13:45:38.299947+00
87	sch_w2	dt_int2	uses	1	{}	2026-02-25 13:45:38.299947+00
88	sch_a16w8	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
89	sch_a16w8	dt_fp16	uses	0.8	{}	2026-02-25 13:45:38.299947+00
90	sch_dyn_a8w8	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
91	sch_stat_a8w8	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
92	sch_dyn_a8w4	dt_int4	uses	0.8	{}	2026-02-25 13:45:38.299947+00
93	sch_dyn_a8w4	dt_int8	uses	0.8	{}	2026-02-25 13:45:38.299947+00
94	sch_dyn_a6w6	dt_fp6_e2m3	uses	0.7	{}	2026-02-25 13:45:38.299947+00
95	sch_dyn_a6w4	dt_int4	uses	0.8	{}	2026-02-25 13:45:38.299947+00
96	sch_dyn_a4w4	dt_int4	uses	1	{}	2026-02-25 13:45:38.299947+00
97	sch_dyn_a4w4	dt_fp4_e2m1	uses	0.6	{}	2026-02-25 13:45:38.299947+00
98	sch_fp8_a8w8	dt_fp8_e4m3	uses	1	{}	2026-02-25 13:45:38.299947+00
99	sch_fp8_a8w8	dt_fp8_e5m2	uses	0.8	{}	2026-02-25 13:45:38.299947+00
100	sch_fp8_kvcache	dt_fp8_e4m3	uses	1	{}	2026-02-25 13:45:38.299947+00
101	sch_qlora	dt_nf4	uses	1	{}	2026-02-25 13:45:38.299947+00
102	sch_qlora	dt_fp16	uses	0.8	{}	2026-02-25 13:45:38.299947+00
103	sch_mixed_2_4	dt_int8	uses	0.7	{}	2026-02-25 13:45:38.299947+00
104	sch_mixed_2_4	dt_fp16	uses	0.8	{}	2026-02-25 13:45:38.299947+00
105	hw_mi300x	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
106	hw_mi300x	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
107	hw_mi300x	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
108	hw_mi300x	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
109	hw_mi300x	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
110	hw_mi300x	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
111	hw_mi300x	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
112	hw_mi325x	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
113	hw_mi325x	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
114	hw_mi325x	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
115	hw_mi325x	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
116	hw_mi325x	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
117	hw_mi325x	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
118	hw_mi325x	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
119	hw_mi350	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
120	hw_mi350	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
121	hw_mi350	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
122	hw_mi350	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
123	hw_mi350	dt_fp4_e2m1	supports	1	{"note": "native CDNA4 FP4"}	2026-02-25 13:45:38.299947+00
124	hw_mi350	dt_fp6_e2m3	supports	1	{"note": "native CDNA4 FP6"}	2026-02-25 13:45:38.299947+00
125	hw_mi350	dt_fp6_e3m2	supports	1	{}	2026-02-25 13:45:38.299947+00
126	hw_mi350	dt_mxfp8	supports	1	{}	2026-02-25 13:45:38.299947+00
127	hw_mi350	dt_mxfp6	supports	1	{}	2026-02-25 13:45:38.299947+00
128	hw_mi350	dt_mxfp4	supports	1	{}	2026-02-25 13:45:38.299947+00
129	hw_rx7900xtx	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
130	hw_rx7900xtx	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
131	hw_rx7900xtx	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
132	hw_rx7900xtx	dt_int4	supports	0.8	{"note": "WMMA IU4 (unsigned INT4 only); not full signed INT4"}	2026-02-25 13:45:38.299947+00
133	hw_b200	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
134	hw_b200	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
135	hw_b200	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
136	hw_b200	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
137	hw_b200	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
138	hw_b200	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
139	hw_b200	dt_fp8_e4m3fn	supports	1	{}	2026-02-25 13:45:38.299947+00
140	hw_b200	dt_fp4_e2m1	supports	1	{"note": "native NVFP4 tensor cores"}	2026-02-25 13:45:38.299947+00
141	hw_b200	dt_fp6_e2m3	supports	1	{"note": "native FP6 tensor cores"}	2026-02-25 13:45:38.299947+00
142	hw_b200	dt_fp6_e3m2	supports	1	{"note": "native FP6 tensor cores"}	2026-02-25 13:45:38.299947+00
143	hw_b200	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
144	hw_b200	dt_mxfp8	supports	0.8	{}	2026-02-25 13:45:38.299947+00
145	hw_b200	dt_mxfp4	supports	0.8	{}	2026-02-25 13:45:38.299947+00
146	hw_gb200	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
147	hw_gb200	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
148	hw_gb200	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
149	hw_gb200	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
150	hw_gb200	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
151	hw_gb200	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
152	hw_gb200	dt_fp4_e2m1	supports	1	{}	2026-02-25 13:45:38.299947+00
153	hw_gb200	dt_fp6_e2m3	supports	1	{}	2026-02-25 13:45:38.299947+00
154	hw_gb200	dt_fp6_e3m2	supports	1	{}	2026-02-25 13:45:38.299947+00
155	hw_gb200	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
156	hw_h100	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
157	hw_h100	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
158	hw_h100	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
159	hw_h100	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
160	hw_h100	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
161	hw_h100	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
162	hw_h100	dt_fp8_e4m3fn	supports	1	{}	2026-02-25 13:45:38.299947+00
163	hw_h100	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
164	hw_h200	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
165	hw_h200	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
166	hw_h200	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
167	hw_h200	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
168	hw_h200	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
169	hw_h200	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
170	hw_h200	dt_fp8_e4m3fn	supports	1	{}	2026-02-25 13:45:38.299947+00
171	hw_h200	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
172	hw_a100	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
173	hw_a100	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
174	hw_a100	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
175	hw_a100	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
176	hw_a100	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
177	hw_a100	dt_int4	supports	1	{"note": "native INT4 tensor core (CC 8.0); last NVIDIA DC GPU with INT4 TC"}	2026-02-25 13:45:38.299947+00
178	hw_l40s	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
179	hw_l40s	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
180	hw_l40s	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
181	hw_l40s	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
182	hw_l40s	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
183	hw_l40s	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
184	hw_l40s	dt_int4	supports	1	{"note": "native Ada INT4 tensor core"}	2026-02-25 13:45:38.299947+00
185	hw_rtx4090	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
186	hw_rtx4090	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
187	hw_rtx4090	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
188	hw_rtx4090	dt_fp8_e4m3	supports	1	{"note": "tensor core GEMM only"}	2026-02-25 13:45:38.299947+00
189	hw_rtx4090	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
190	hw_rtx4090	dt_int4	supports	1	{"note": "native Ada INT4 tensor core"}	2026-02-25 13:45:38.299947+00
191	hw_rtx5090	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
192	hw_rtx5090	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
193	hw_rtx5090	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
194	hw_rtx5090	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
195	hw_rtx5090	dt_fp8_e5m2	supports	1	{}	2026-02-25 13:45:38.299947+00
196	hw_rtx5090	dt_fp4_e2m1	supports	1	{"note": "native Blackwell FP4 (NVFP4)"}	2026-02-25 13:45:38.299947+00
197	hw_rtx5090	dt_fp6_e2m3	supports	1	{"note": "native Blackwell FP6"}	2026-02-25 13:45:38.299947+00
198	hw_rtx5090	dt_fp6_e3m2	supports	1	{}	2026-02-25 13:45:38.299947+00
199	hw_rtx5090	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
200	hw_npu_qualcomm	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
201	hw_npu_qualcomm	dt_int4	supports	0.9	{"note": "weight INT4 via HTP"}	2026-02-25 13:45:38.299947+00
202	hw_npu_qualcomm	dt_fp16	supports	0.8	{}	2026-02-25 13:45:38.299947+00
203	hw_npu_intel	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
204	hw_npu_mediatek	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
205	hw_npu_mediatek	dt_int4	supports	0.7	{}	2026-02-25 13:45:38.299947+00
206	hw_apple_m4	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
207	hw_apple_m4	dt_int8	supports	1	{"note": "W8A8 optimised on Neural Engine"}	2026-02-25 13:45:38.299947+00
208	hw_apple_m4_ultra	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
209	hw_apple_m4_ultra	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
210	hw_tpu_v5e	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
211	hw_tpu_v5e	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
212	hw_gaudi3	dt_fp32	supports	1	{}	2026-02-25 13:45:38.299947+00
213	hw_gaudi3	dt_tf32	supports	1	{}	2026-02-25 13:45:38.299947+00
214	hw_gaudi3	dt_bf16	supports	1	{}	2026-02-25 13:45:38.299947+00
215	hw_gaudi3	dt_fp16	supports	1	{}	2026-02-25 13:45:38.299947+00
216	hw_gaudi3	dt_fp8_e4m3	supports	1	{}	2026-02-25 13:45:38.299947+00
217	hw_gaudi3	dt_int8	supports	1	{}	2026-02-25 13:45:38.299947+00
218	hw_mi300x	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
219	hw_mi300x	sch_stat_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
220	hw_mi300x	sch_a16w8	supports	1	{}	2026-02-25 13:45:38.299947+00
221	hw_mi325x	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
222	hw_h100	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
223	hw_h100	sch_stat_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
224	hw_h200	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
225	hw_a100	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
226	hw_a100	sch_stat_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
227	hw_l40s	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
228	hw_gb200	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
229	hw_gaudi3	sch_dyn_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
230	hw_mi300x	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
231	hw_mi300x	sch_fp8_kvcache	supports	1	{}	2026-02-25 13:45:38.299947+00
232	hw_mi325x	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
233	hw_h100	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
234	hw_h100	sch_fp8_kvcache	supports	1	{}	2026-02-25 13:45:38.299947+00
235	hw_h200	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
236	hw_h200	sch_fp8_kvcache	supports	1	{}	2026-02-25 13:45:38.299947+00
237	hw_b200	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
238	hw_b200	sch_fp8_kvcache	supports	1	{}	2026-02-25 13:45:38.299947+00
239	hw_gb200	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
240	hw_l40s	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
241	hw_rtx4090	sch_fp8_a8w8	supports	0.9	{"note": "GEMM only"}	2026-02-25 13:45:38.299947+00
242	hw_rtx5090	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
243	hw_mi350	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
244	hw_gaudi3	sch_fp8_a8w8	supports	1	{}	2026-02-25 13:45:38.299947+00
245	hw_a100	sch_mixed_2_4	supports	1	{"note": "native 2:4 structured sparsity"}	2026-02-25 13:45:38.299947+00
246	hw_h100	sch_mixed_2_4	supports	1	{}	2026-02-25 13:45:38.299947+00
247	hw_b200	sch_mixed_2_4	supports	1	{}	2026-02-25 13:45:38.299947+00
248	hw_mi300x	sch_w4	supports	0.8	{"note": "no native INT4; dequant to FP16/INT8 via vLLM/AutoGPTQ ROCm kernels"}	2026-02-25 13:45:38.299947+00
249	hw_mi325x	sch_w4	supports	0.8	{"note": "no native INT4; dequant to FP16/INT8 via vLLM ROCm kernels"}	2026-02-25 13:45:38.299947+00
250	hw_h100	sch_w4	supports	0.9	{"note": "no native INT4 TC (CC 9.0); dequant to FP16 via Marlin/vLLM CUDA kernels"}	2026-02-25 13:45:38.299947+00
251	hw_h200	sch_w4	supports	0.9	{"note": "no native INT4 TC (CC 9.0); dequant to FP16 via Marlin/vLLM"}	2026-02-25 13:45:38.299947+00
252	hw_a100	sch_w4	supports	1	{"note": "native INT4 tensor core (CC 8.0); direct INT4 GEMM"}	2026-02-25 13:45:38.299947+00
253	hw_b200	sch_w4	supports	0.8	{"note": "no native INT4 TC (CC 10.0); dequant to FP16 or use FP4 path instead"}	2026-02-25 13:45:38.299947+00
254	hw_gb200	sch_w4	supports	0.8	{"note": "no native INT4 TC; dequant to FP16 or use FP4 path"}	2026-02-25 13:45:38.299947+00
255	hw_l40s	sch_w4	supports	1	{"note": "native INT4 tensor core (CC 8.9)"}	2026-02-25 13:45:38.299947+00
256	hw_rtx4090	sch_w4	supports	1	{"note": "native INT4 tensor core (CC 8.9)"}	2026-02-25 13:45:38.299947+00
257	hw_rtx5090	sch_w4	supports	0.8	{"note": "no native INT4 TC (CC 10.3); dequant to FP16 or use FP4 path"}	2026-02-25 13:45:38.299947+00
258	hw_rx7900xtx	sch_w4	supports	0.9	{"note": "WMMA IU4 (unsigned only) + ROCm GPTQ dequant kernels"}	2026-02-25 13:45:38.299947+00
259	hw_mi350	sch_w4	supports	0.8	{"note": "no native INT4; can use FP4 path or dequant to FP16"}	2026-02-25 13:45:38.299947+00
260	hw_apple_m4	sch_w4	supports	0.7	{"note": "via llama.cpp / CoreML dequant"}	2026-02-25 13:45:38.299947+00
261	hw_apple_m4_ultra	sch_w4	supports	0.8	{}	2026-02-25 13:45:38.299947+00
262	hw_npu_qualcomm	sch_w4	supports	0.8	{"note": "HTP INT4 weight quantization"}	2026-02-25 13:45:38.299947+00
263	hw_npu_mediatek	sch_w4	supports	0.5	{}	2026-02-25 13:45:38.299947+00
264	hw_gaudi3	sch_w4	supports	0.6	{"note": "no native INT4; via Intel Neural Compressor dequant"}	2026-02-25 13:45:38.299947+00
265	hw_mi300x	sch_w4_g128	supports	0.8	{"note": "no native INT4; dequant path"}	2026-02-25 13:45:38.299947+00
266	hw_h100	sch_w4_g128	supports	0.9	{"note": "no native INT4; dequant to FP16"}	2026-02-25 13:45:38.299947+00
267	hw_b200	sch_w4_g128	supports	0.8	{"note": "no native INT4; dequant path"}	2026-02-25 13:45:38.299947+00
268	hw_a100	sch_w4_g128	supports	1	{"note": "native INT4 tensor core (CC 8.0)"}	2026-02-25 13:45:38.299947+00
269	hw_l40s	sch_w4_g128	supports	1	{"note": "native INT4 tensor core (CC 8.9)"}	2026-02-25 13:45:38.299947+00
270	hw_rtx4090	sch_w4_g128	supports	1	{"note": "native INT4 tensor core (CC 8.9)"}	2026-02-25 13:45:38.299947+00
271	hw_rtx5090	sch_w4_g128	supports	0.8	{"note": "no native INT4; dequant path"}	2026-02-25 13:45:38.299947+00
272	hw_mi300x	sch_qlora	supports	0.9	{}	2026-02-25 13:45:38.299947+00
273	hw_h100	sch_qlora	supports	0.9	{}	2026-02-25 13:45:38.299947+00
274	hw_a100	sch_qlora	supports	0.8	{}	2026-02-25 13:45:38.299947+00
275	hw_rtx4090	sch_qlora	supports	0.9	{}	2026-02-25 13:45:38.299947+00
276	hw_rtx5090	sch_qlora	supports	1	{}	2026-02-25 13:45:38.299947+00
277	hw_b200	sch_dyn_a4w4	supports	1	{"note": "via native NVFP4 tensor cores (FP4 E2M1)"}	2026-02-25 13:45:38.299947+00
278	hw_gb200	sch_dyn_a4w4	supports	1	{"note": "via native NVFP4 tensor cores"}	2026-02-25 13:45:38.299947+00
279	hw_rtx5090	sch_dyn_a4w4	supports	0.9	{"note": "via native NVFP4 tensor cores"}	2026-02-25 13:45:38.299947+00
280	hw_mi350	sch_dyn_a4w4	supports	0.9	{"note": "via native CDNA4 FP4 (E2M1)"}	2026-02-25 13:45:38.299947+00
281	hw_a100	sch_dyn_a4w4	supports	0.8	{"note": "via native INT4 tensor cores (CC 8.0); ATOM/QuiK target this"}	2026-02-25 13:45:38.299947+00
282	hw_l40s	sch_dyn_a4w4	supports	0.9	{"note": "via native INT4 tensor cores (CC 8.9)"}	2026-02-25 13:45:38.299947+00
283	hw_rtx4090	sch_dyn_a4w4	supports	0.9	{"note": "via native INT4 tensor cores (CC 8.9)"}	2026-02-25 13:45:38.299947+00
284	algo_rtn	dt_int2	uses	0.7	{}	2026-02-25 13:45:38.299947+00
285	algo_rtn	dt_int3	uses	0.7	{}	2026-02-25 13:45:38.299947+00
286	algo_rtn	dt_fp16	uses	0.7	{}	2026-02-25 13:45:38.299947+00
287	algo_hqq	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
288	algo_omniquant	dt_int2	uses	0.7	{}	2026-02-25 13:45:38.299947+00
289	algo_omniquant	dt_int3	uses	0.7	{}	2026-02-25 13:45:38.299947+00
290	algo_quarot	dt_int8	uses	1	{}	2026-02-25 13:45:38.299947+00
291	algo_owq	dt_int3	uses	0.7	{}	2026-02-25 13:45:38.299947+00
\.


--
-- Data for Name: knowledge_nodes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.knowledge_nodes (id, label, node_type, category, metadata_json, created_at) FROM stdin;
dt_fp32	FP32	data_type	traditional	{"bits": 32, "format": "IEEE 754"}	2026-02-25 13:45:38.299947+00
dt_fp16	FP16	data_type	traditional	{"bits": 16, "format": "IEEE 754"}	2026-02-25 13:45:38.299947+00
dt_bf16	BF16	data_type	traditional	{"bits": 16, "format": "Brain Float"}	2026-02-25 13:45:38.299947+00
dt_tf32	TF32	data_type	traditional	{"bits": 19, "note": "NVIDIA 19-bit internal", "format": "TensorFloat-32"}	2026-02-25 13:45:38.299947+00
dt_int8	INT8	data_type	traditional	{"bits": 8, "format": "integer"}	2026-02-25 13:45:38.299947+00
dt_int4	INT4	data_type	traditional	{"bits": 4, "format": "integer"}	2026-02-25 13:45:38.299947+00
dt_int3	INT3	data_type	traditional	{"bits": 3, "format": "integer"}	2026-02-25 13:45:38.299947+00
dt_int2	INT2	data_type	traditional	{"bits": 2, "format": "integer"}	2026-02-25 13:45:38.299947+00
dt_fp8_e4m3	FP8 E4M3	data_type	fp8	{"bits": 8, "format": "FP8", "exponent": 4, "mantissa": 3}	2026-02-25 13:45:38.299947+00
dt_fp8_e5m2	FP8 E5M2	data_type	fp8	{"bits": 8, "format": "FP8", "exponent": 5, "mantissa": 2}	2026-02-25 13:45:38.299947+00
dt_fp8_e4m3fn	FP8 E4M3FN	data_type	fp8	{"bits": 8, "note": "NVIDIA variant", "format": "FP8 (no inf)"}	2026-02-25 13:45:38.299947+00
dt_fp4_e2m1	FP4 E2M1	data_type	low_precision	{"bits": 4, "note": "Blackwell native", "format": "FP4"}	2026-02-25 13:45:38.299947+00
dt_fp6_e2m3	FP6 E2M3	data_type	low_precision	{"bits": 6, "format": "FP6"}	2026-02-25 13:45:38.299947+00
dt_fp6_e3m2	FP6 E3M2	data_type	low_precision	{"bits": 6, "format": "FP6"}	2026-02-25 13:45:38.299947+00
dt_nf4	NF4	data_type	special	{"bits": 4, "note": "QLoRA format", "format": "Normal Float"}	2026-02-25 13:45:38.299947+00
dt_ternary	Ternary (1.58-bit)	data_type	special	{"bits": 1.58, "format": "ternary", "values": "{-1, 0, 1}"}	2026-02-25 13:45:38.299947+00
dt_binary	Binary (1-bit)	data_type	special	{"bits": 1, "format": "binary", "values": "{-1, 1}"}	2026-02-25 13:45:38.299947+00
dt_mxfp8	MXFP8	data_type	mx	{"bits": 8, "format": "Microscaling", "block_size": 32}	2026-02-25 13:45:38.299947+00
dt_mxfp6	MXFP6	data_type	mx	{"bits": 6, "format": "Microscaling", "block_size": 32}	2026-02-25 13:45:38.299947+00
dt_mxfp4	MXFP4	data_type	mx	{"bits": 4, "format": "Microscaling", "block_size": 32}	2026-02-25 13:45:38.299947+00
dt_mxint8	MXINT8	data_type	mx	{"bits": 8, "format": "Microscaling", "block_size": 32}	2026-02-25 13:45:38.299947+00
dt_mxint4	MXINT4	data_type	mx	{"bits": 4, "format": "Microscaling", "block_size": 32}	2026-02-25 13:45:38.299947+00
hw_mi300x	AMD MI300X	hardware	amd_dc	{"arch": "CDNA3", "note": "INT4 not a native matrix core type; used as storage format dequantized to FP16/INT8 for compute", "family": "Instinct", "vendor": "AMD", "memory_gb": 192, "int4_native": false, "tflops_fp16": 1307, "hbm_bandwidth_tb": 5.3, "matrix_core_types": "FP64,FP32,TF32,FP16,BF16,FP8(E4M3/E5M2-FNUZ),INT8", "compute_capability": "CDNA3"}	2026-02-25 13:45:38.299947+00
hw_mi325x	AMD MI325X	hardware	amd_dc	{"arch": "CDNA3", "family": "Instinct", "vendor": "AMD", "memory_gb": 256, "int4_native": false, "hbm_bandwidth_tb": 6.0, "matrix_core_types": "FP64,FP32,TF32,FP16,BF16,FP8(E4M3/E5M2-FNUZ),INT8", "compute_capability": "CDNA3"}	2026-02-25 13:45:38.299947+00
hw_mi350	AMD MI350	hardware	amd_dc	{"arch": "CDNA4", "note": "2025", "family": "Instinct", "vendor": "AMD", "matrix_core_types": "FP16,BF16,FP8,FP6(E2M3/E3M2),FP4(E2M1),INT8,MXFP8,MXFP6,MXFP4"}	2026-02-25 13:45:38.299947+00
hw_rx7900xtx	AMD RX 7900 XTX	hardware	amd_consumer	{"arch": "RDNA3", "type": "consumer", "family": "Radeon", "vendor": "AMD", "memory_gb": 24, "wmma_types": "FP16,BF16,INT8,IU4(unsigned INT4)"}	2026-02-25 13:45:38.299947+00
hw_b200	NVIDIA B200 Blackwell	hardware	nvidia_dc	{"arch": "Blackwell", "note": "Blackwell dropped INT4 tensor cores; uses FP4 E2M1 (NVFP4) instead", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 192, "fp4_tflops": 9000, "int4_native": false, "tflops_fp16": 2250, "tensor_types": "FP64,TF32,BF16,FP16,FP8,FP6,FP4,INT8", "tensor_core_gen": 5, "compute_capability": "10.0"}	2026-02-25 13:45:38.299947+00
hw_gb200	NVIDIA GB200 Grace-Blackwell	hardware	nvidia_dc	{"arch": "Blackwell", "note": "NVLink 1.8TB/s", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 384, "int4_native": false, "tensor_types": "FP64,TF32,BF16,FP16,FP8,FP6,FP4,INT8", "compute_capability": "10.0"}	2026-02-25 13:45:38.299947+00
hw_h100	NVIDIA H100 Hopper	hardware	nvidia_dc	{"arch": "Hopper", "note": "Hopper dropped INT4 tensor cores from Ampere; FP8 added", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 80, "int4_native": false, "tflops_fp16": 989, "tensor_types": "FP64,TF32,BF16,FP16,FP8,INT8", "tensor_core_gen": 4, "compute_capability": "9.0"}	2026-02-25 13:45:38.299947+00
hw_h200	NVIDIA H200	hardware	nvidia_dc	{"arch": "Hopper", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 141, "int4_native": false, "tensor_types": "FP64,TF32,BF16,FP16,FP8,INT8", "hbm_bandwidth_tb": 4.8, "compute_capability": "9.0"}	2026-02-25 13:45:38.299947+00
hw_a100	NVIDIA A100 Ampere	hardware	nvidia_dc	{"arch": "Ampere", "note": "Last NVIDIA DC GPU with native INT4 tensor cores; no FP8", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 80, "int4_native": true, "tflops_fp16": 312, "tensor_types": "FP64,TF32,BF16,FP16,INT8,INT4", "tensor_core_gen": 3, "compute_capability": "8.0"}	2026-02-25 13:45:38.299947+00
hw_l40s	NVIDIA L40S	hardware	nvidia_dc	{"arch": "Ada Lovelace", "family": "Datacenter", "vendor": "NVIDIA", "memory_gb": 48, "int4_native": true, "tensor_types": "TF32,BF16,FP16,FP8,INT8,INT4", "tensor_core_gen": 4, "compute_capability": "8.9"}	2026-02-25 13:45:38.299947+00
hw_rtx4090	NVIDIA RTX 4090	hardware	nvidia_consumer	{"arch": "Ada Lovelace", "type": "consumer", "family": "GeForce", "vendor": "NVIDIA", "memory_gb": 24, "int4_native": true, "tensor_types": "TF32,BF16,FP16,FP8,INT8,INT4", "tensor_core_gen": 4, "compute_capability": "8.9"}	2026-02-25 13:45:38.299947+00
hw_rtx5090	NVIDIA RTX 5090	hardware	nvidia_consumer	{"arch": "Blackwell", "type": "consumer", "family": "GeForce", "vendor": "NVIDIA", "memory_gb": 32, "int4_native": false, "tensor_types": "TF32,BF16,FP16,FP8,FP6,FP4,INT8", "tensor_core_gen": 5, "compute_capability": "10.3"}	2026-02-25 13:45:38.299947+00
hw_npu_qualcomm	Qualcomm Hexagon NPU	hardware	npu	{"arch": "Hexagon", "type": "NPU", "family": "NPU", "target": "mobile", "vendor": "Qualcomm"}	2026-02-25 13:45:38.299947+00
hw_npu_intel	Intel Meteor Lake NPU	hardware	npu	{"arch": "Meteor Lake", "type": "NPU", "family": "NPU", "target": "laptop", "vendor": "Intel"}	2026-02-25 13:45:38.299947+00
hw_npu_mediatek	MediaTek APU	hardware	npu	{"arch": "APU", "type": "NPU", "family": "NPU", "target": "mobile", "vendor": "MediaTek"}	2026-02-25 13:45:38.299947+00
hw_apple_m4	Apple M4 (MPS)	hardware	apple	{"arch": "M4", "family": "Apple Silicon", "vendor": "Apple", "memory_gb": 32}	2026-02-25 13:45:38.299947+00
hw_apple_m4_ultra	Apple M4 Ultra	hardware	apple	{"arch": "M4", "family": "Apple Silicon", "vendor": "Apple", "memory_gb": 192}	2026-02-25 13:45:38.299947+00
hw_tpu_v5e	Google TPU v5e	hardware	tpu	{"arch": "TPU v5e", "type": "TPU", "family": "TPU", "vendor": "Google", "memory_gb": 16}	2026-02-25 13:45:38.299947+00
hw_gaudi3	Intel Gaudi 3	hardware	intel_dc	{"arch": "Gaudi 3", "family": "Gaudi", "vendor": "Intel", "memory_gb": 128}	2026-02-25 13:45:38.299947+00
sch_a16w8	A16W8 (weight-only 8b)	scheme	weight_only	{"dynamic": false, "act_bits": 16, "weight_bits": 8}	2026-02-25 13:45:38.299947+00
sch_w4	W4 (weight-only 4-bit)	scheme	weight_only	{"act_bits": 16, "weight_bits": 4}	2026-02-25 13:45:38.299947+00
sch_w3	W3 (weight-only 3-bit)	scheme	weight_only	{"act_bits": 16, "weight_bits": 3}	2026-02-25 13:45:38.299947+00
sch_w2	W2 (weight-only 2-bit)	scheme	weight_only	{"act_bits": 16, "weight_bits": 2}	2026-02-25 13:45:38.299947+00
sch_w4_g128	W4G128 (grouped 4-bit)	scheme	weight_only	{"act_bits": 16, "group_size": 128, "weight_bits": 4}	2026-02-25 13:45:38.299947+00
sch_dyn_a8w8	Dynamic A8W8	scheme	w_a	{"dynamic": true, "act_bits": 8, "weight_bits": 8}	2026-02-25 13:45:38.299947+00
sch_stat_a8w8	Static A8W8	scheme	w_a	{"dynamic": false, "act_bits": 8, "weight_bits": 8}	2026-02-25 13:45:38.299947+00
sch_dyn_a8w4	Dynamic A8W4	scheme	w_a	{"dynamic": true, "act_bits": 8, "weight_bits": 4}	2026-02-25 13:45:38.299947+00
sch_dyn_a6w6	Dynamic A6W6	scheme	w_a	{"dynamic": true, "act_bits": 6, "weight_bits": 6}	2026-02-25 13:45:38.299947+00
sch_dyn_a6w4	Dynamic A6W4	scheme	w_a	{"dynamic": true, "act_bits": 6, "weight_bits": 4}	2026-02-25 13:45:38.299947+00
sch_dyn_a4w4	Dynamic A4W4	scheme	w_a	{"dynamic": true, "act_bits": 4, "weight_bits": 4}	2026-02-25 13:45:38.299947+00
sch_fp8_a8w8	FP8 W8A8	scheme	fp8_scheme	{"format": "FP8", "act_bits": 8, "weight_bits": 8}	2026-02-25 13:45:38.299947+00
sch_fp8_kvcache	FP8 KV-Cache	scheme	fp8_scheme	{"note": "KV cache compression", "format": "FP8", "cache_bits": 8}	2026-02-25 13:45:38.299947+00
sch_mixed_2_4	Mixed 2:4 Sparsity	scheme	mixed	{"note": "Structural sparsity", "sparsity": "2:4"}	2026-02-25 13:45:38.299947+00
sch_qlora	QLoRA (NF4+FP16)	scheme	mixed	{"note": "Efficient fine-tuning", "format": "NF4", "weight_bits": 4, "adapter_bits": 16}	2026-02-25 13:45:38.299947+00
algo_gptq	GPTQ	algorithm	ptq_weight	{"tags": ["weight_only", "ptq", "hessian", "4bit", "3bit", "iclr"], "type": "PTQ", "year": 2022, "paper": "arXiv:2210.17323", "scope": "weight-only", "title": "GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers", "venue": "ICLR 2023", "authors": ["Elias Frantar", "Saleh Ashkboos", "Torsten Hoefler", "Dan Alistarh"], "arxiv_id": "2210.17323", "citation": "@article{frantar2022gptq,\\n  title={GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers},\\n  author={Frantar, Elias and Ashkboos, Saleh and Hoefler, Torsten and Alistarh, Dan},\\n  journal={arXiv preprint arXiv:2210.17323},\\n  year={2022}\\n}\\n", "datasets": "WikiText-2, PTB, C4", "core_idea": "GPTQ uses approximate second-order information (Hessian) to minimize quantization\\nerror layer by layer. It processes weights column by column, quantizing each and\\ncompensating the error in the remaining unquantized weights.\\n\\nKey innovation: Uses a lazy batch update scheme that processes multiple columns\\ntogether, reducing the computational overhead while maintaining accuracy.\\n", "calibration": "yes", "description": "Hessian-based layer-wise quantization; column-by-column with error compensation", "expected_behavior": "- Achieves good accuracy at 4-bit and even 3-bit quantization\\n- Processes one layer at a time (memory efficient)\\n- Requires calibration data for Hessian computation\\n- Runtime scales with model size but is generally fast (minutes for 7B models)\\n- Works well across different model architectures\\n", "known_limitations": "- Requires sufficient calibration data for accurate Hessian estimation\\n- Column-by-column processing can accumulate errors\\n- May struggle with very aggressive quantization (2-bit)\\n- Sensitive to the quality of calibration data\\n- Does not handle activation quantization\\n", "relevant_equations": "Optimal update: δ_F = -w_q · (H^-1)_qq · H_q:\\n\\nWhere w_q is the quantization error for column q, H is the Hessian approximation\\n(H = 2X^T X for the layer input X), and the update is applied to remaining columns.\\n\\nThe Hessian diagonal approximation: H_ii ≈ sum_j (x_ij)^2\\n"}	2026-02-25 13:45:38.299947+00
algo_awq	AWQ	algorithm	ptq_weight	{"tags": ["weight_only", "ptq", "4bit", "activation_aware", "mlsys"], "type": "PTQ", "year": 2023, "paper": "arXiv:2306.00978", "scope": "weight-only", "title": "AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration", "venue": "MLSys 2024", "authors": ["Ji Lin", "Jiaming Tang", "Haotian Tang", "Shang Yang", "Xingyu Dang", "Song Han"], "arxiv_id": "2306.00978", "citation": "@article{lin2023awq,\\n  title={AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration},\\n  author={Lin, Ji and Tang, Jiaming and Tang, Haotian and Yang, Shang and Dang, Xingyu and Han, Song},\\n  journal={arXiv preprint arXiv:2306.00978},\\n  year={2023}\\n}\\n", "datasets": "WikiText-2, PTB, C4, LAMBADA", "core_idea": "AWQ protects salient weights based on activation magnitude rather than weight magnitude.\\nThe key insight is that only ~1% of weights are critical for LLM performance, and these\\ncan be identified by observing which weights correspond to large activation values.\\n\\nInstead of mixed-precision (which is hardware-unfriendly), AWQ searches for optimal\\nper-channel scaling factors that reduce quantization error for salient weights while\\nkeeping the format uniform.\\n", "calibration": "yes", "description": "Activation-aware Weight Quantization; protects salient weights by activation magnitude", "expected_behavior": "- Achieves <1% accuracy degradation at 4-bit for most LLMs\\n- Works without retraining or backpropagation\\n- Requires calibration data (typically 128 samples)\\n- Best suited for weight-only quantization\\n- Provides 3-4x speedup on hardware with INT4 support\\n", "known_limitations": "- Primarily designed for 4-bit; may not be optimal for other bit widths\\n- Requires activation statistics from calibration data\\n- Per-channel scaling adds some overhead\\n- May not handle extreme outliers as well as methods like SmoothQuant\\n", "relevant_equations": "Optimal scale: s* = argmin_s ||Q(W·s) · (s^-1 · X) - W · X||\\n\\nWhere Q is the quantization function, W is the weight matrix, X is the activation,\\nand s is the per-channel scaling factor.\\n"}	2026-02-25 13:45:38.299947+00
algo_hqq	HQQ	algorithm	ptq_weight	{"type": "PTQ", "year": 2023, "scope": "weight-only", "calibration": "no"}	2026-02-25 13:45:38.299947+00
algo_rtn	RTN	algorithm	ptq_weight	{"note": "Round-to-Nearest baseline", "type": "PTQ", "year": 2020, "scope": "weight-only"}	2026-02-25 13:45:38.299947+00
algo_spqr	SpQR	algorithm	ptq_weight	{"type": "PTQ", "year": 2023, "scope": "weight-only"}	2026-02-25 13:45:38.299947+00
algo_owq	OWQ	algorithm	ptq_weight	{"type": "PTQ", "year": 2023, "scope": "weight-only", "arxiv_id": "2306.02272", "datasets": "Zero-shot (HellaSwag, etc.); OPT, LLaMA, BLOOM", "calibration": "yes", "description": "Outlier-aware; mixed-precision weak columns (FP16) + low-bit rest, Hessian-based"}	2026-02-25 13:45:38.299947+00
algo_qlora	QLoRA	algorithm	ptq_weight	{"note": "NF4 quantized fine-tuning", "type": "PTQ+FT", "year": 2023, "paper": "arXiv:2305.14314", "scope": "weight-only"}	2026-02-25 13:45:38.299947+00
algo_squeezellm	SqueezeLLM	algorithm	ptq_weight	{"note": "Dense-and-sparse quantization", "type": "PTQ", "year": 2023, "scope": "weight-only"}	2026-02-25 13:45:38.299947+00
algo_smoothquant	SmoothQuant	algorithm	ptq_wa	{"tags": ["weight_activation", "ptq", "8bit", "w8a8", "outlier_handling", "icml"], "type": "PTQ", "year": 2022, "paper": "arXiv:2211.10438", "scope": "W+A", "title": "SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models", "venue": "ICML 2023", "authors": ["Guangxuan Xiao", "Ji Lin", "Mickael Seznec", "Hao Wu", "Julien Demouth", "Song Han"], "arxiv_id": "2211.10438", "citation": "@article{xiao2022smoothquant,\\n  title={SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models},\\n  author={Xiao, Guangxuan and Lin, Ji and Seznec, Mickael and Wu, Hao and Demouth, Julien and Han, Song},\\n  journal={arXiv preprint arXiv:2211.10438},\\n  year={2022}\\n}\\n", "datasets": "WikiText-2, PTB, C4, LAMBADA", "core_idea": "SmoothQuant addresses the challenge of quantizing both weights AND activations (W8A8).\\nThe key insight is that activation outliers make activation quantization difficult,\\nbut these outliers are systematic and predictable.\\n\\nThe solution: mathematically migrate the quantization difficulty from activations\\nto weights by applying a per-channel smoothing transformation. This is done by\\ndividing activations by a scale factor and multiplying weights by the same factor.\\n", "calibration": "yes", "description": "Migrates activation outliers to weights via per-channel smoothing; W8A8", "expected_behavior": "- Enables W8A8 quantization with minimal accuracy loss\\n- Works with both weight and activation quantization\\n- Provides ~2x speedup with INT8 tensor cores\\n- Requires calibration data to compute smoothing factors\\n- Best results with α = 0.5 for most models\\n", "known_limitations": "- Primarily designed for INT8 (W8A8), not lower bit widths\\n- Requires per-channel smoothing factors (storage overhead)\\n- May not fully eliminate all outliers in extreme cases\\n- The smoothing transformation must be fused into the model\\n- Not suitable for weight-only quantization scenarios\\n", "relevant_equations": "Smoothing transformation:\\nY = (X · diag(s)^-1) · (diag(s) · W) = X̂ · Ŵ\\n\\nOptimal scale: s_j = max(|X_j|)^α / max(|W_j|)^(1-α)\\n\\nWhere α ∈ [0,1] controls the migration strength (typically α = 0.5)\\n"}	2026-02-25 13:45:38.299947+00
algo_quarot	QuaRot	algorithm	ptq_wa	{"note": "Hadamard rotation eliminates outliers; uniform 4-bit for weights, activations, and KV cache", "type": "PTQ", "year": 2024, "paper": "arXiv:2404.00456", "scope": "W+A", "venue": "NeurIPS 2024", "arxiv_id": "2404.00456", "datasets": "WikiText-2", "calibration": "yes", "description": "Rotation-based (Hadamard); W4A4KV4, outlier suppression via fixed rotations"}	2026-02-25 13:45:38.299947+00
algo_llmint8	LLM.int8()	algorithm	ptq_wa	{"type": "PTQ", "year": 2022, "paper": "arXiv:2208.07339", "scope": "W+A"}	2026-02-25 13:45:38.299947+00
algo_zeroquant	ZeroQuant	algorithm	ptq_wa	{"type": "PTQ", "year": 2022, "paper": "arXiv:2206.01861", "scope": "W+A", "arxiv_id": "2303.08302", "datasets": "WikiText-2, C4; GLUE (CoLA, QNLI, etc.) for BERT/RoBERTa", "calibration": "yes", "description": "Efficient PTQ; layer-wise knowledge distillation, supports data-free in some modes"}	2026-02-25 13:45:38.299947+00
algo_atom	ATOM	algorithm	ptq_wa	{"note": "Mixed-precision W4A4 with fine-grained quantization; uses INT4 for both weights and activations", "type": "PTQ", "year": 2023, "paper": "arXiv:2310.19102", "scope": "W+A", "venue": "MLSys 2024"}	2026-02-25 13:45:38.299947+00
algo_quik	QuiK	algorithm	ptq_wa	{"note": "INT4 weight + INT4 activation (W4A4) with outlier columns kept in higher precision", "type": "PTQ", "year": 2023, "paper": "arXiv:2310.09259", "scope": "W+A", "venue": "EMNLP 2024"}	2026-02-25 13:45:38.299947+00
algo_omniquant	OmniQuant	algorithm	ptq_mixed	{"type": "PTQ", "year": 2023, "scope": "mixed", "arxiv_id": "2308.13137", "datasets": "C4 (PPL), PIQA, BoolQ, ARC-Easy, ARC-Challenge, HellaSwag, WinoGrande", "calibration": "yes", "description": "Learnable quantization; block-wise optimization, 128 calibration samples"}	2026-02-25 13:45:38.299947+00
algo_paretoq	ParetoQ	algorithm	qat	{"note": "Unified framework for 1-bit to 4-bit QAT; ternary/2b/3b use Stretched Elastic Quant (SEQ)", "type": "QAT", "year": 2025, "paper": "arXiv:2502.02631", "scope": "mixed-precision", "arxiv_id": "2502.02631", "datasets": "ARC-Easy, ARC-Challenge, BoolQ, PIQA, HellaSwag, WinoGrande", "calibration": "yes", "description": "Extremely low-bit scaling laws; ternary and sub-2-bit"}	2026-02-25 13:45:38.299947+00
algo_fp8quant	FP8 Quantization	algorithm	ptq_wa	{"note": "vLLM/TensorRT FP8 flow", "type": "PTQ", "year": 2023, "scope": "W+A"}	2026-02-25 13:45:38.299947+00
algo_kvcache_quant	KV-Cache Quantization	algorithm	ptq_mixed	{"note": "Compress KV cache to FP8/INT8", "type": "PTQ", "year": 2024, "scope": "kv-cache"}	2026-02-25 13:45:38.299947+00
algo_bitnet	BitNet	algorithm	qat	{"type": "QAT", "year": 2023, "paper": "arXiv:2310.11453", "scope": "1-bit"}	2026-02-25 13:45:38.299947+00
algo_qat_generic	QAT (generic)	algorithm	qat	{"note": "Quantization-Aware Training", "type": "QAT", "year": 2020, "scope": "configurable"}	2026-02-25 13:45:38.299947+00
\.


--
-- Data for Name: layer_metrics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.layer_metrics (id, experiment_id, quant_config_id, created_at, layer_index, layer_name, layer_type, stat_name, stat_type, value, histogram_bins, histogram_counts, extra_metadata) FROM stdin;
\.


--
-- Data for Name: metrics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metrics (id, experiment_id, quant_config_id, created_at, dataset, split, metric_name, value, extra_metadata) FROM stdin;
358	2107	\N	2026-03-03 17:01:20.627949+00	wikitext2	test	perplexity	27.654335021972656	{}
359	2100	\N	2026-03-03 17:01:51.083916+00	wikitext2	test	perplexity	33.47077178955078	{}
360	2099	\N	2026-03-03 17:01:54.781364+00	wikitext2	test	perplexity	54.22998046875	{}
361	2108	\N	2026-03-03 17:03:05.034979+00	wikitext2	test	perplexity	22.003400802612305	{}
362	2091	\N	2026-03-03 17:03:31.796941+00	wikitext2	test	perplexity	23.93115997314453	{}
363	2109	\N	2026-03-03 17:03:42.542372+00	wikitext2	test	perplexity	14.624337196350098	{}
364	2090	\N	2026-03-03 17:03:53.097181+00	wikitext2	test	perplexity	32.093910217285156	{}
365	2110	\N	2026-03-03 17:04:11.861284+00	wikitext2	test	perplexity	12.471220970153809	{}
366	2092	\N	2026-03-03 17:04:21.800762+00	wikitext2	test	perplexity	15.284322738647461	{}
367	2111	\N	2026-03-03 17:04:23.26706+00	wikitext2	test	perplexity	10.860077857971191	{}
368	2112	\N	2026-03-03 17:06:36.522468+00	wikitext2	test	perplexity	10.128074645996094	{}
369	2115	\N	2026-03-03 17:07:11.294747+00	wikitext2	test	perplexity	23.762182235717773	{}
370	2093	\N	2026-03-03 17:07:19.186208+00	wikitext2	test	perplexity	12.663372039794922	{}
371	2101	\N	2026-03-03 17:07:42.226789+00	wikitext2	test	perplexity	20.776094436645508	{}
372	2116	\N	2026-03-03 17:07:47.509941+00	wikitext2	test	perplexity	18.773937225341797	{}
373	2117	\N	2026-03-03 17:09:47.389541+00	wikitext2	test	perplexity	16.114028930664062	{}
374	2124	\N	2026-03-03 17:13:30.234396+00	wikitext2	test	perplexity	10.555431365966797	{}
375	2124	\N	2026-03-03 17:13:30.234396+00	lambada	test	accuracy	68.50378420337667	{}
376	2102	\N	2026-03-03 17:14:57.172302+00	wikitext2	test	perplexity	17.032825469970703	{}
377	2125	\N	2026-03-03 17:15:04.746009+00	wikitext2	test	perplexity	5.681406021118164	{}
378	2118	\N	2026-03-03 17:18:43.353229+00	wikitext2	test	perplexity	14.024920463562012	{}
379	2136	\N	2026-03-03 17:20:21.692511+00	wikitext2	test	perplexity	5.472134590148926	{}
380	2127	\N	2026-03-03 17:24:46.574608+00	wikitext2	test	perplexity	5.476658821105957	{}
381	2094	\N	2026-03-03 17:24:48.944256+00	wikitext2	test	perplexity	11.100260734558105	{}
382	2126	\N	2026-03-03 17:26:04.458197+00	wikitext2	test	perplexity	5.092390060424805	{}
383	2132	\N	2026-03-03 17:26:11.987019+00	wikitext2	test	perplexity	5.253581523895264	{}
384	2103	\N	2026-03-03 17:29:35.41927+00	wikitext2	test	perplexity	12.89018726348877	{}
385	2104	\N	2026-03-03 17:32:45.391735+00	wikitext2	test	perplexity	11.611163139343262	{}
386	2119	\N	2026-03-03 17:34:54.37005+00	wikitext2	test	perplexity	11.709453582763672	{}
387	2148	\N	2026-03-03 17:35:49.37632+00	c4	test	perplexity	26.564287185668945	{}
388	2149	\N	2026-03-03 17:36:30.058773+00	c4	test	perplexity	16.070068359375	{}
389	2135	\N	2026-03-03 17:37:21.068922+00	wikitext2	test	perplexity	5.664186000823975	{}
390	2150	\N	2026-03-03 17:37:33.217934+00	c4	test	perplexity	14.34252643585205	{}
391	2151	\N	2026-03-03 17:38:37.074862+00	c4	test	perplexity	12.712713241577148	{}
392	2152	\N	2026-03-03 17:39:16.080149+00	c4	test	perplexity	12.05894947052002	{}
393	2095	\N	2026-03-03 17:39:39.883798+00	wikitext2	test	perplexity	10.28785514831543	{}
394	2133	\N	2026-03-03 17:42:33.140388+00	wikitext2	test	perplexity	4870817	{}
395	2123	\N	2026-03-03 17:52:42.479877+00	wikitext2	test	perplexity	10.563092231750488	{}
396	2123	\N	2026-03-03 17:52:42.479877+00	lambada	test	accuracy	68.42615951872696	{}
397	2146	\N	2026-03-03 19:12:26.377304+00	wikitext2	test	perplexity	4.185610294342041	{}
398	2147	\N	2026-03-03 19:46:38.442853+00	wikitext2	test	perplexity	6.080111026763916	{}
399	2139	\N	2026-03-03 19:57:55.235836+00	wikitext2	test	perplexity	5.805197715759277	{}
400	2143	\N	2026-03-03 20:43:07.264087+00	wikitext2	test	perplexity	6.240464210510254	{}
401	2140	\N	2026-03-03 20:43:36.947783+00	wikitext2	test	perplexity	5.17585563659668	{}
402	2134	\N	2026-03-03 21:52:51.855403+00	wikitext2	test	perplexity	5.6110053062438965	{}
411	2208	\N	2026-03-03 22:37:32.561172+00	wikitext2	test	perplexity	9.558215141296387	{}
412	2219	\N	2026-03-03 22:40:00.431037+00	wikitext2	test	perplexity	27.654335021972656	{}
413	2220	\N	2026-03-03 22:40:28.188198+00	wikitext2	test	perplexity	22.003400802612305	{}
414	2221	\N	2026-03-03 22:40:55.285626+00	wikitext2	test	perplexity	14.624337196350098	{}
415	2222	\N	2026-03-03 22:41:47.416732+00	wikitext2	test	perplexity	12.471220970153809	{}
416	2223	\N	2026-03-03 22:42:45.862395+00	wikitext2	test	perplexity	10.860077857971191	{}
417	2224	\N	2026-03-03 22:43:50.816813+00	wikitext2	test	perplexity	10.128074645996094	{}
418	2225	\N	2026-03-03 22:45:50.122928+00	wikitext2	test	perplexity	9.558215141296387	{}
419	2226	\N	2026-03-03 22:52:02.666553+00	wikitext2	test	perplexity	9.339207649230957	{}
420	2228	\N	2026-03-03 22:52:54.301431+00	wikitext2	test	perplexity	22.41301918029785	{}
421	2229	\N	2026-03-03 22:53:40.392416+00	wikitext2	test	perplexity	17.685869216918945	{}
422	2230	\N	2026-03-03 22:54:17.967177+00	wikitext2	test	perplexity	15.387137413024902	{}
423	2218	\N	2026-03-03 22:54:32.137038+00	wikitext2	test	perplexity	1008997.3125	{}
424	2231	\N	2026-03-03 22:55:07.210878+00	wikitext2	test	perplexity	13.480436325073242	{}
425	2210	\N	2026-03-03 22:55:19.133993+00	wikitext2	test	perplexity	4.885620594024658	{}
426	2232	\N	2026-03-03 22:55:38.198013+00	wikitext2	test	perplexity	11.366668701171875	{}
427	2236	\N	2026-03-03 22:56:54.160108+00	wikitext2	test	perplexity	5.6771626472473145	{}
428	2237	\N	2026-03-03 22:58:45.357327+00	wikitext2	test	perplexity	5.0906524658203125	{}
429	2238	\N	2026-03-03 23:00:03.829014+00	wikitext2	test	perplexity	5.472134590148926	{}
430	2239	\N	2026-03-03 23:00:57.775694+00	wikitext2	test	perplexity	4.883795738220215	{}
431	2235	\N	2026-03-03 23:02:09.45291+00	wikitext2	test	perplexity	10.555431365966797	{}
432	2235	\N	2026-03-03 23:02:09.45291+00	lambada	test	accuracy	68.50378420337667	{}
433	2243	\N	2026-03-03 23:03:11.428164+00	wikitext2	test	perplexity	5.252070903778076	{}
434	2240	\N	2026-03-03 23:05:41.215897+00	wikitext2	test	perplexity	3.31925630569458	{}
435	2244	\N	2026-03-03 23:06:38.479769+00	wikitext2	test	perplexity	3.8418986797332764	{}
436	2248	\N	2026-03-03 23:09:38.061179+00	wikitext2	test	perplexity	5.6771626472473145	{}
437	2249	\N	2026-03-03 23:11:08.163083+00	wikitext2	test	perplexity	5.0906524658203125	{}
438	2250	\N	2026-03-03 23:13:47.75738+00	wikitext2	test	perplexity	4.1006340980529785	{}
439	2251	\N	2026-03-03 23:19:14.020705+00	wikitext2	test	perplexity	3.532062292098999	{}
440	2252	\N	2026-03-03 23:22:37.603258+00	wikitext2	test	perplexity	4.138036727905273	{}
441	2253	\N	2026-03-03 23:23:47.964828+00	wikitext2	test	perplexity	5.9483819007873535	{}
442	2254	\N	2026-03-03 23:24:12.932721+00	c4	test	perplexity	26.564287185668945	{}
443	2255	\N	2026-03-03 23:24:59.816442+00	c4	test	perplexity	16.070068359375	{}
444	2256	\N	2026-03-03 23:25:42.973277+00	c4	test	perplexity	14.34252643585205	{}
445	2257	\N	2026-03-03 23:26:36.16537+00	c4	test	perplexity	12.712713241577148	{}
446	2258	\N	2026-03-03 23:27:53.236535+00	c4	test	perplexity	12.05894947052002	{}
447	2261	\N	2026-03-03 23:29:02.166318+00	wikitext2	test	perplexity	6.239816188812256	{}
448	2245	\N	2026-03-04 00:16:38.491022+00	wikitext2	test	perplexity	5.472134590148926	{}
449	2246	\N	2026-03-04 00:39:54.559908+00	wikitext2	test	perplexity	4.883795738220215	{}
450	2216	\N	2026-03-04 02:15:12.306406+00	wikitext2	test	perplexity	5.312376976013184	{}
451	2212	\N	2026-03-04 03:18:03.504636+00	wikitext2	test	perplexity	4.96562385559082	{}
452	2214	\N	2026-03-04 03:54:15.702098+00	wikitext2	test	perplexity	4.213266372680664	{}
453	2262	\N	2026-03-04 07:09:17.487907+00	wikitext2	test	perplexity	9.558215141296387	{}
454	2263	\N	2026-03-04 07:18:27.821275+00	wikitext2	test	perplexity	4.8852033615112305	{}
498	2482	\N	2026-03-04 09:00:17.785368+00	c4	test	perplexity	26.564287185668945	{}
499	2482	\N	2026-03-04 09:00:17.785368+00	wikitext2	test	perplexity	27.654335021972656	{}
500	2483	\N	2026-03-04 09:00:31.277517+00	c4	test	perplexity	22.589452743530273	{}
501	2483	\N	2026-03-04 09:00:31.277517+00	wikitext2	test	perplexity	22.003400802612305	{}
502	2484	\N	2026-03-04 09:00:41.2887+00	c4	test	perplexity	16.070068359375	{}
503	2484	\N	2026-03-04 09:00:41.2887+00	wikitext2	test	perplexity	14.624337196350098	{}
504	2485	\N	2026-03-04 09:01:26.592803+00	c4	test	perplexity	14.34252643585205	{}
505	2485	\N	2026-03-04 09:01:26.592803+00	wikitext2	test	perplexity	12.471220970153809	{}
506	2486	\N	2026-03-04 09:02:03.555602+00	c4	test	perplexity	12.712713241577148	{}
507	2486	\N	2026-03-04 09:02:03.555602+00	wikitext2	test	perplexity	10.860077857971191	{}
508	2487	\N	2026-03-04 09:02:19.785918+00	c4	test	perplexity	12.05894947052002	{}
509	2491	\N	2026-03-04 09:03:46.747747+00	c4	test	perplexity	26.594755172729492	{}
510	2491	\N	2026-03-04 09:03:46.747747+00	wikitext2	test	perplexity	22.41301918029785	{}
511	2492	\N	2026-03-04 09:04:06.451526+00	c4	test	perplexity	22.047826766967773	{}
512	2492	\N	2026-03-04 09:04:06.451526+00	wikitext2	test	perplexity	17.685869216918945	{}
513	2493	\N	2026-03-04 09:05:11.313536+00	c4	test	perplexity	19.48792839050293	{}
514	2493	\N	2026-03-04 09:05:11.313536+00	wikitext2	test	perplexity	15.387137413024902	{}
515	2488	\N	2026-03-04 09:05:40.181877+00	c4	test	perplexity	11.444765090942383	{}
516	2488	\N	2026-03-04 09:05:40.181877+00	wikitext2	test	perplexity	9.558215141296387	{}
517	2494	\N	2026-03-04 09:05:50.264754+00	c4	test	perplexity	17.481931686401367	{}
518	2494	\N	2026-03-04 09:05:50.264754+00	wikitext2	test	perplexity	13.480436325073242	{}
519	2495	\N	2026-03-04 09:06:32.903863+00	c4	test	perplexity	15.198158264160156	{}
520	2506	\N	2026-03-04 09:31:58.029555+00	wikitext2	test	perplexity	5.252070903778076	{}
521	2506	\N	2026-03-04 09:31:58.029555+00	hellaswag	test	accuracy	81.15913164708225	{}
522	2506	\N	2026-03-04 09:31:58.029555+00	lambada	test	accuracy	75.2571317679022	{}
523	2506	\N	2026-03-04 09:31:58.029555+00	piqa	test	accuracy	82.53536452665942	{}
524	2506	\N	2026-03-04 09:31:58.029555+00	winogrande	test	accuracy	75.37490134175216	{}
525	2499	\N	2026-03-04 09:40:32.815212+00	hellaswag	test	accuracy	76.04062935670186	{}
526	2499	\N	2026-03-04 09:40:32.815212+00	lambada	test	accuracy	73.76285658839511	{}
527	2499	\N	2026-03-04 09:40:32.815212+00	piqa	test	accuracy	79.27094668117519	{}
528	2499	\N	2026-03-04 09:40:32.815212+00	winogrande	test	accuracy	70.1657458563536	{}
529	2507	\N	2026-03-04 10:43:01.398928+00	wikitext2	test	perplexity	3.8418986797332764	{}
530	2507	\N	2026-03-04 10:43:01.398928+00	hellaswag	test	accuracy	84.20633339972116	{}
531	2507	\N	2026-03-04 10:43:01.398928+00	lambada	test	accuracy	77.50824762274404	{}
532	2507	\N	2026-03-04 10:43:01.398928+00	piqa	test	accuracy	83.29706202393906	{}
533	2507	\N	2026-03-04 10:43:01.398928+00	winogrande	test	accuracy	76.87450670876085	{}
534	2508	\N	2026-03-04 10:44:02.123483+00	wikitext2	test	perplexity	5.472134590148926	{}
535	2511	\N	2026-03-04 11:54:20.037411+00	wikitext2	test	perplexity	5.6771626472473145	{}
536	2512	\N	2026-03-04 12:38:56.072369+00	wikitext2	test	perplexity	5.0906524658203125	{}
537	2509	\N	2026-03-04 12:40:21.860872+00	wikitext2	test	perplexity	4.883795738220215	{}
538	2517	\N	2026-03-04 12:41:27.463041+00	c4	test	perplexity	26.564287185668945	{}
539	2518	\N	2026-03-04 12:42:02.10871+00	c4	test	perplexity	16.070068359375	{}
540	2519	\N	2026-03-04 12:42:46.928047+00	c4	test	perplexity	14.34252643585205	{}
541	2520	\N	2026-03-04 12:43:46.453332+00	c4	test	perplexity	12.712713241577148	{}
542	2521	\N	2026-03-04 12:45:11.345089+00	c4	test	perplexity	12.05894947052002	{}
543	2524	\N	2026-03-04 13:38:46.305329+00	wikitext2	test	perplexity	6.239816188812256	{}
544	2524	\N	2026-03-04 13:38:46.305329+00	arc_challenge	test	accuracy	54.94880546075085	{}
545	2524	\N	2026-03-04 13:38:46.305329+00	arc_easy	test	accuracy	82.53367003367003	{}
546	2524	\N	2026-03-04 13:38:46.305329+00	hellaswag	test	accuracy	79.30691097390958	{}
547	2524	\N	2026-03-04 13:38:46.305329+00	piqa	test	accuracy	81.17519042437432	{}
548	2524	\N	2026-03-04 13:38:46.305329+00	winogrande	test	accuracy	74.5067087608524	{}
549	2525	\N	2026-03-04 13:41:09.159866+00	c4	test	perplexity	29.42350959777832	{}
550	2525	\N	2026-03-04 13:41:09.159866+00	wikitext2	test	perplexity	32.332096099853516	{}
551	2526	\N	2026-03-04 13:45:44.054691+00	c4	test	perplexity	24.16202163696289	{}
552	2526	\N	2026-03-04 13:45:44.054691+00	wikitext2	test	perplexity	24.015775680541992	{}
553	2527	\N	2026-03-04 13:53:46.550394+00	c4	test	perplexity	16.721641540527344	{}
554	2527	\N	2026-03-04 13:53:46.550394+00	wikitext2	test	perplexity	15.42032241821289	{}
555	2528	\N	2026-03-04 14:06:27.927283+00	c4	test	perplexity	14.850454330444336	{}
556	2528	\N	2026-03-04 14:06:27.927283+00	wikitext2	test	perplexity	12.734235763549805	{}
557	2529	\N	2026-03-04 14:17:44.809978+00	c4	test	perplexity	12.999029159545898	{}
558	2529	\N	2026-03-04 14:17:44.809978+00	wikitext2	test	perplexity	11.183184623718262	{}
559	2534	\N	2026-03-04 14:21:58.774276+00	c4	test	perplexity	41.779056549072266	{}
560	2534	\N	2026-03-04 14:21:58.774276+00	wikitext2	test	perplexity	53.439144134521484	{}
561	2535	\N	2026-03-04 14:26:59.180579+00	c4	test	perplexity	30.223129272460938	{}
562	2535	\N	2026-03-04 14:26:59.180579+00	wikitext2	test	perplexity	32.1961555480957	{}
563	2530	\N	2026-03-04 14:35:07.169179+00	c4	test	perplexity	NaN	{}
564	2530	\N	2026-03-04 14:35:07.169179+00	wikitext2	test	perplexity	NaN	{}
565	2537	\N	2026-03-04 14:47:46.731478+00	c4	test	perplexity	17.54319190979004	{}
566	2537	\N	2026-03-04 14:47:46.731478+00	wikitext2	test	perplexity	16.74315643310547	{}
567	2538	\N	2026-03-04 14:54:25.817161+00	c4	test	perplexity	14.56210994720459	{}
568	2538	\N	2026-03-04 14:54:25.817161+00	wikitext2	test	perplexity	12.743741989135742	{}
569	2542	\N	2026-03-04 14:56:30.240217+00	c4	test	perplexity	26.564287185668945	{}
570	2542	\N	2026-03-04 14:56:30.240217+00	wikitext2	test	perplexity	27.654335021972656	{}
571	2543	\N	2026-03-04 14:57:38.88795+00	c4	test	perplexity	22.589452743530273	{}
572	2543	\N	2026-03-04 14:57:38.88795+00	wikitext2	test	perplexity	22.003400802612305	{}
573	2544	\N	2026-03-04 14:58:42.659496+00	c4	test	perplexity	16.070068359375	{}
574	2544	\N	2026-03-04 14:58:42.659496+00	wikitext2	test	perplexity	14.624337196350098	{}
575	2545	\N	2026-03-04 15:00:01.968172+00	c4	test	perplexity	14.34252643585205	{}
576	2545	\N	2026-03-04 15:00:01.968172+00	wikitext2	test	perplexity	12.471220970153809	{}
577	2546	\N	2026-03-04 15:01:49.071774+00	c4	test	perplexity	12.712713241577148	{}
578	2546	\N	2026-03-04 15:01:49.071774+00	wikitext2	test	perplexity	10.860077857971191	{}
579	2547	\N	2026-03-04 15:04:32.852902+00	c4	test	perplexity	12.05894947052002	{}
580	2547	\N	2026-03-04 15:04:32.852902+00	wikitext2	test	perplexity	10.128074645996094	{}
581	2550	\N	2026-03-04 15:10:26.392083+00	c4	test	perplexity	27.803314208984375	{}
582	2550	\N	2026-03-04 15:10:26.392083+00	wikitext2	test	perplexity	23.814661026000977	{}
583	2539	\N	2026-03-04 15:11:25.026892+00	c4	test	perplexity	NaN	{}
584	2539	\N	2026-03-04 15:11:25.026892+00	wikitext2	test	perplexity	NaN	{}
585	2551	\N	2026-03-04 15:15:17.79469+00	c4	test	perplexity	23.018651962280273	{}
586	2551	\N	2026-03-04 15:15:17.79469+00	wikitext2	test	perplexity	18.92437744140625	{}
587	2552	\N	2026-03-04 15:18:00.894768+00	c4	test	perplexity	20.243610382080078	{}
588	2552	\N	2026-03-04 15:18:00.894768+00	wikitext2	test	perplexity	16.167781829833984	{}
589	2553	\N	2026-03-04 15:26:43.711388+00	c4	test	perplexity	17.995769500732422	{}
590	2553	\N	2026-03-04 15:26:43.711388+00	wikitext2	test	perplexity	13.992049217224121	{}
591	2513	\N	2026-03-04 15:31:12.589204+00	wikitext2	test	perplexity	4.1006340980529785	{}
592	2562	\N	2026-03-04 17:05:17.666994+00	wikitext2	test	perplexity	5.474919319152832	{}
593	2562	\N	2026-03-04 17:05:17.666994+00	hellaswag	test	accuracy	76.1202947619996	{}
594	2562	\N	2026-03-04 17:05:17.666994+00	lambada	test	accuracy	73.64641956142053	{}
595	2562	\N	2026-03-04 17:05:17.666994+00	piqa	test	accuracy	78.45484221980414	{}
596	2562	\N	2026-03-04 17:05:17.666994+00	winogrande	test	accuracy	69.37647987371744	{}
597	2563	\N	2026-03-04 17:12:35.406355+00	wikitext2	test	perplexity	4.885721206665039	{}
598	2563	\N	2026-03-04 17:12:35.406355+00	hellaswag	test	accuracy	79.61561441943836	{}
599	2563	\N	2026-03-04 17:12:35.406355+00	lambada	test	accuracy	76.53793906462255	{}
600	2563	\N	2026-03-04 17:12:35.406355+00	piqa	test	accuracy	80.52230685527746	{}
601	2563	\N	2026-03-04 17:12:35.406355+00	winogrande	test	accuracy	72.37569060773481	{}
602	2567	\N	2026-03-04 17:18:38.491171+00	wikitext2	test	perplexity	5.252322673797607	{}
603	2567	\N	2026-03-04 17:18:38.491171+00	hellaswag	test	accuracy	81.24875522804223	{}
604	2567	\N	2026-03-04 17:18:38.491171+00	lambada	test	accuracy	75.27653793906462	{}
605	2567	\N	2026-03-04 17:18:38.491171+00	piqa	test	accuracy	82.64417845484222	{}
606	2567	\N	2026-03-04 17:18:38.491171+00	winogrande	test	accuracy	75.37490134175216	{}
607	2571	\N	2026-03-04 19:42:46.237979+00	wikitext2	test	perplexity	5.472134590148926	{}
608	2570	\N	2026-03-04 19:43:26.274935+00	wikitext2	test	perplexity	5.642966270446777	{}
609	2569	\N	2026-03-04 20:45:21.943485+00	wikitext2	test	perplexity	5.6026763916015625	{}
610	2574	\N	2026-03-04 23:28:21.72494+00	wikitext2	test	perplexity	5.80198860168457	{}
611	2572	\N	2026-03-05 00:44:03.736978+00	wikitext2	test	perplexity	4.9732985496521	{}
612	2575	\N	2026-03-05 01:27:46.492401+00	wikitext2	test	perplexity	5.171350955963135	{}
613	2583	\N	2026-03-05 02:08:51.348598+00	c4	test	perplexity	26.564287185668945	{}
614	2584	\N	2026-03-05 02:09:32.884879+00	c4	test	perplexity	16.070068359375	{}
615	2585	\N	2026-03-05 02:10:25.511602+00	c4	test	perplexity	14.34252643585205	{}
616	2586	\N	2026-03-05 02:11:33.328906+00	c4	test	perplexity	12.712713241577148	{}
617	2587	\N	2026-03-05 02:13:08.211909+00	c4	test	perplexity	12.05894947052002	{}
618	2578	\N	2026-03-05 03:23:40.735363+00	wikitext2	test	perplexity	6.168704509735107	{}
619	2581	\N	2026-03-05 04:50:17.787786+00	wikitext2	test	perplexity	4.197564125061035	{}
620	2629	\N	2026-03-05 08:48:09.926727+00	c4	test	perplexity	10.988639831542969	{}
621	2629	\N	2026-03-05 08:48:09.926727+00	wikitext2	test	perplexity	9.339207649230957	{}
622	2633	\N	2026-03-05 09:17:13.965323+00	wikitext2	test	perplexity	10.555431365966797	{}
623	2633	\N	2026-03-05 09:17:13.965323+00	hellaswag	test	accuracy	70.7329217287393	{}
624	2633	\N	2026-03-05 09:17:13.965323+00	lambada	test	accuracy	68.50378420337667	{}
625	2633	\N	2026-03-05 09:17:13.965323+00	piqa	test	accuracy	78.23721436343853	{}
626	2633	\N	2026-03-05 09:17:13.965323+00	winogrande	test	accuracy	67.71902131018153	{}
627	2634	\N	2026-03-05 09:43:40.614403+00	wikitext2	test	perplexity	5.0906524658203125	{}
628	2634	\N	2026-03-05 09:43:40.614403+00	hellaswag	test	accuracy	79.3168691495718	{}
629	2634	\N	2026-03-05 09:43:40.614403+00	lambada	test	accuracy	75.68406753347564	{}
630	2634	\N	2026-03-05 09:43:40.614403+00	piqa	test	accuracy	79.92383025027203	{}
631	2634	\N	2026-03-05 09:43:40.614403+00	winogrande	test	accuracy	73.24388318863457	{}
632	2635	\N	2026-03-05 10:05:24.618865+00	wikitext2	test	perplexity	5.472134590148926	{}
633	2635	\N	2026-03-05 10:05:24.618865+00	hellaswag	test	accuracy	76.18004381597291	{}
634	2635	\N	2026-03-05 10:05:24.618865+00	lambada	test	accuracy	73.64641956142053	{}
635	2635	\N	2026-03-05 10:05:24.618865+00	piqa	test	accuracy	78.72687704026116	{}
636	2635	\N	2026-03-05 10:05:24.618865+00	winogrande	test	accuracy	69.45540647198106	{}
637	2636	\N	2026-03-05 10:32:01.199631+00	wikitext2	test	perplexity	4.883795738220215	{}
638	2636	\N	2026-03-05 10:32:01.199631+00	hellaswag	test	accuracy	79.62557259510058	{}
639	2636	\N	2026-03-05 10:32:01.199631+00	lambada	test	accuracy	76.53793906462255	{}
640	2636	\N	2026-03-05 10:32:01.199631+00	piqa	test	accuracy	80.35908596300327	{}
641	2636	\N	2026-03-05 10:32:01.199631+00	winogrande	test	accuracy	72.45461720599842	{}
642	2637	\N	2026-03-05 11:40:45.147036+00	wikitext2	test	perplexity	3.31925630569458	{}
643	2637	\N	2026-03-05 11:40:45.147036+00	hellaswag	test	accuracy	84.33578968333	{}
644	2637	\N	2026-03-05 11:40:45.147036+00	lambada	test	accuracy	79.46827091014943	{}
645	2637	\N	2026-03-05 11:40:45.147036+00	piqa	test	accuracy	82.53536452665942	{}
646	2637	\N	2026-03-05 11:40:45.147036+00	winogrande	test	accuracy	80.26835043409629	{}
647	2640	\N	2026-03-05 14:40:50.367856+00	wikitext2	test	perplexity	3.31925630569458	{}
648	2641	\N	2026-03-05 17:34:51.900054+00	wikitext2	test	perplexity	3.532062292098999	{}
649	2642	\N	2026-03-05 19:31:08.401199+00	wikitext2	test	perplexity	4.138036727905273	{}
650	2650	\N	2026-03-05 21:36:47.450021+00	c4	test	perplexity	11.444765090942383	{}
651	2650	\N	2026-03-05 21:36:47.450021+00	wikitext2	test	perplexity	9.558215141296387	{}
652	2652	\N	2026-03-05 21:47:16.249766+00	c4	test	perplexity	15.536419868469238	{}
653	2652	\N	2026-03-05 21:47:16.249766+00	wikitext2	test	perplexity	11.701807022094727	{}
654	2656	\N	2026-03-05 23:22:35.099974+00	wikitext2	test	perplexity	10.560441017150879	{}
655	2656	\N	2026-03-05 23:22:35.099974+00	hellaswag	test	accuracy	70.75283808006373	{}
656	2656	\N	2026-03-05 23:22:35.099974+00	lambada	test	accuracy	68.5814088880264	{}
657	2656	\N	2026-03-05 23:22:35.099974+00	piqa	test	accuracy	78.40043525571274	{}
658	2656	\N	2026-03-05 23:22:35.099974+00	winogrande	test	accuracy	67.95580110497238	{}
659	2657	\N	2026-03-05 23:49:31.662819+00	wikitext2	test	perplexity	10.555431365966797	{}
660	2657	\N	2026-03-05 23:49:31.662819+00	hellaswag	test	accuracy	70.7329217287393	{}
661	2657	\N	2026-03-05 23:49:31.662819+00	lambada	test	accuracy	68.50378420337667	{}
662	2657	\N	2026-03-05 23:49:31.662819+00	piqa	test	accuracy	78.23721436343853	{}
663	2657	\N	2026-03-05 23:49:31.662819+00	winogrande	test	accuracy	67.71902131018153	{}
664	2658	\N	2026-03-06 00:37:09.452712+00	wikitext2	test	perplexity	5.680202960968018	{}
665	2658	\N	2026-03-06 00:37:09.452712+00	hellaswag	test	accuracy	76.02071300537742	{}
666	2658	\N	2026-03-06 00:37:09.452712+00	lambada	test	accuracy	73.84048127304483	{}
667	2658	\N	2026-03-06 00:37:09.452712+00	piqa	test	accuracy	79.32535364526659	{}
668	2658	\N	2026-03-06 00:37:09.452712+00	winogrande	test	accuracy	70.40252565114443	{}
669	2662	\N	2026-03-06 04:27:51.114059+00	wikitext2	test	perplexity	4805887	{}
670	2662	\N	2026-03-06 04:27:51.114059+00	hellaswag	test	accuracy	26.180043815972915	{}
671	2662	\N	2026-03-06 04:27:51.114059+00	piqa	test	accuracy	50.81610446137106	{}
672	2662	\N	2026-03-06 04:27:51.114059+00	winogrande	test	accuracy	48.697711128650354	{}
673	2664	\N	2026-03-06 11:51:26.718879+00	wikitext2	test	perplexity	4.2170729637146	{}
674	2666	\N	2026-03-06 23:44:45.633356+00	wikitext2	test	perplexity	5.298691272735596	{}
675	2668	\N	2026-03-07 02:58:18.736427+00	wikitext2	test	perplexity	6.05887508392334	{}
\.


--
-- Data for Name: paper_notes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.paper_notes (id, paper_id, created_at, updated_at, title, authors, year, venue, arxiv_id, doi, citation, core_idea, relevant_equations, expected_behavior, known_limitations, method_names, tags, extra_metadata) FROM stdin;
\.


--
-- Data for Name: quant_configs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.quant_configs (id, experiment_id, created_at, method_name, method_version, bit_width, per_channel, is_symmetric, group_size, activation_quant, activation_bits, kv_quant, kv_bits, stack_order, parent_config_id, config_json, calib_dataset, calib_size, calib_seq_length, status, error_message, duration_seconds) FROM stdin;
2095	2098	2026-03-03 16:58:52.928329+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2103	2106	2026-03-03 16:58:52.951728+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2110	2113	2026-03-03 16:58:52.964257+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2111	2114	2026-03-03 16:58:52.965714+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2117	2120	2026-03-03 16:58:52.974552+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2118	2121	2026-03-03 16:58:52.975985+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2119	2122	2026-03-03 16:58:52.977709+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2125	2128	2026-03-03 16:58:52.987518+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2126	2129	2026-03-03 16:58:52.988927+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2127	2130	2026-03-03 16:58:52.990369+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2128	2131	2026-03-03 16:58:52.991812+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2134	2137	2026-03-03 16:58:53.000683+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2135	2138	2026-03-03 16:58:53.002147+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2138	2141	2026-03-03 16:58:53.007048+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2139	2142	2026-03-03 16:58:53.008504+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2141	2144	2026-03-03 16:58:53.011397+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2142	2145	2026-03-03 16:58:53.013064+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2150	2153	2026-03-03 16:58:53.024954+00	gptq	\N	2	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2104	2107	2026-03-03 16:58:52.954562+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.001992464065551758
2097	2100	2026-03-03 16:58:52.935521+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	107.18722820281982
2096	2099	2026-03-03 16:58:52.931887+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	53.68801689147949
2105	2108	2026-03-03 16:58:52.956226+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.0031490325927734375
2088	2091	2026-03-03 16:58:52.906285+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	104.82923817634583
2106	2109	2026-03-03 16:58:52.957837+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.003084421157836914
2087	2090	2026-03-03 16:58:52.892718+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	49.69095802307129
2107	2110	2026-03-03 16:58:52.959639+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.003899812698364258
2089	2092	2026-03-03 16:58:52.909624+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	176.29172253608704
2108	2111	2026-03-03 16:58:52.961225+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.0039560794830322266
2109	2112	2026-03-03 16:58:52.96279+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.004730701446533203
2112	2115	2026-03-03 16:58:52.967134+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	109.8017590045929
2090	2093	2026-03-03 16:58:52.912817+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	424.86224031448364
2098	2101	2026-03-03 16:58:52.938236+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	350.8161334991455
2113	2116	2026-03-03 16:58:52.96883+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	126.35223937034607
2114	2117	2026-03-03 16:58:52.970278+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	225.5021185874939
2121	2124	2026-03-03 16:58:52.981442+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0.005720376968383789
2099	2102	2026-03-03 16:58:52.940826+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	733.4785313606262
2122	2125	2026-03-03 16:58:52.98289+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	360.45048570632935
2115	2118	2026-03-03 16:58:52.971704+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	752.4944076538086
2133	2136	2026-03-03 16:58:52.99925+00	rtn	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0.004060983657836914
2124	2127	2026-03-03 16:58:52.986076+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	728.6029291152954
2091	2094	2026-03-03 16:58:52.916784+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1270.002168893814
2123	2126	2026-03-03 16:58:52.984349+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	924.393726348877
2129	2132	2026-03-03 16:58:52.993328+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	533.6150803565979
2100	2103	2026-03-03 16:58:52.943603+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1720.656921863556
2101	2104	2026-03-03 16:58:52.946553+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1721.064491033554
2116	2119	2026-03-03 16:58:52.973139+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1680.3201177120209
2145	2148	2026-03-03 16:58:53.017464+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.002057313919067383
2146	2149	2026-03-03 16:58:53.018899+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0030143260955810547
2132	2135	2026-03-03 16:58:52.997809+00	gptq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	1084.170182466507
2147	2150	2026-03-03 16:58:53.020355+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0036773681640625
2148	2151	2026-03-03 16:58:53.021999+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0038902759552001953
2149	2152	2026-03-03 16:58:53.023463+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.00455474853515625
2092	2095	2026-03-03 16:58:52.919854+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	2292.8821229934692
2130	2133	2026-03-03 16:58:52.994919+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	1302.9903938770294
2120	2123	2026-03-03 16:58:52.979201+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	1542.9823648929596
2093	2096	2026-03-03 16:58:52.922682+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	4479.187019824982
2102	2105	2026-03-03 16:58:52.949048+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	5184.820996046066
2094	2097	2026-03-03 16:58:52.925594+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	7355.984870195389
2143	2146	2026-03-03 16:58:53.014541+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	5690.485975027084
2144	2147	2026-03-03 16:58:53.016001+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	7872.896415233612
2136	2139	2026-03-03 16:58:53.004072+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	9097.89717745781
2140	2143	2026-03-03 16:58:53.009955+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	11503.901487827301
2137	2140	2026-03-03 16:58:53.00559+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	11777.528771162033
2131	2134	2026-03-03 16:58:52.996369+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	12182.44649362564
2479	2482	2026-03-04 08:59:45.651302+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2518	2521	2026-03-04 08:59:45.884413+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2482	2485	2026-03-04 08:59:45.670417+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2526	2529	2026-03-04 08:59:45.957922+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1071.6704292297363
2230	2233	2026-03-03 22:35:03.638985+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2231	2234	2026-03-03 22:35:03.641171+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2206	2209	2026-03-03 22:34:54.510813+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2208	2211	2026-03-03 22:34:54.527305+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2214	2217	2026-03-03 22:34:54.576344+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2224	2227	2026-03-03 22:35:03.625596+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2238	2241	2026-03-03 22:35:03.656862+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2239	2242	2026-03-03 22:35:03.659075+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2244	2247	2026-03-03 22:35:03.670436+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2256	2259	2026-03-03 22:35:03.697613+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	8	2048	pending	\N	\N
2257	2260	2026-03-03 22:35:03.699858+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	8	2048	pending	\N	\N
2205	2208	2026-03-03 22:34:54.488767+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.005408763885498047
2216	2219	2026-03-03 22:35:03.605563+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2217	2220	2026-03-03 22:35:03.609025+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2218	2221	2026-03-03 22:35:03.611505+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2219	2222	2026-03-03 22:35:03.613983+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2220	2223	2026-03-03 22:35:03.616346+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2221	2224	2026-03-03 22:35:03.618688+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2222	2225	2026-03-03 22:35:03.621113+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2223	2226	2026-03-03 22:35:03.623354+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2225	2228	2026-03-03 22:35:03.627902+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2226	2229	2026-03-03 22:35:03.630154+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2227	2230	2026-03-03 22:35:03.632351+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2215	2218	2026-03-03 22:34:54.583661+00	gptq	\N	2	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	830.8856372833252
2228	2231	2026-03-03 22:35:03.634619+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2207	2210	2026-03-03 22:34:54.519229+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	1069.4847922325134
2229	2232	2026-03-03 22:35:03.636778+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2233	2236	2026-03-03 22:35:03.645679+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2234	2237	2026-03-03 22:35:03.647931+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2235	2238	2026-03-03 22:35:03.650141+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2236	2239	2026-03-03 22:35:03.652397+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2232	2235	2026-03-03 22:35:03.643438+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2240	2243	2026-03-03 22:35:03.661274+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2237	2240	2026-03-03 22:35:03.654694+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2241	2244	2026-03-03 22:35:03.663473+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2245	2248	2026-03-03 22:35:03.672631+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2246	2249	2026-03-03 22:35:03.674857+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2247	2250	2026-03-03 22:35:03.677397+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2248	2251	2026-03-03 22:35:03.679691+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2249	2252	2026-03-03 22:35:03.682006+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2250	2253	2026-03-03 22:35:03.684263+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2251	2254	2026-03-03 22:35:03.686494+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2252	2255	2026-03-03 22:35:03.688703+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2253	2256	2026-03-03 22:35:03.690933+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2254	2257	2026-03-03 22:35:03.693103+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2255	2258	2026-03-03 22:35:03.695401+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2258	2261	2026-03-03 22:35:03.702106+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2242	2245	2026-03-03 22:35:03.665881+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2243	2246	2026-03-03 22:35:03.6682+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2213	2216	2026-03-03 22:34:54.568702+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	12906.144008874893
2209	2212	2026-03-03 22:34:54.535215+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	11229.35829257965
2211	2214	2026-03-03 22:34:54.550988+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	18899.183861732483
2210	2213	2026-03-03 22:34:54.543082+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	23496.103397607803
2212	2215	2026-03-03 22:34:54.560836+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	29261.938007593155
2261	2264	2026-03-04 07:06:59.62329+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2262	2265	2026-03-04 07:06:59.630786+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2263	2266	2026-03-04 07:06:59.638006+00	gptq	\N	2	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2264	2267	2026-03-04 07:06:59.645422+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2259	2262	2026-03-04 07:06:59.597859+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.005357980728149414
2260	2263	2026-03-04 07:06:59.615588+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	596.6102952957153
2485	2488	2026-03-04 08:59:45.678828+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2540	2543	2026-03-04 08:59:45.990359+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.003086090087890625
2682	2685	2026-03-08 08:52:15.225232+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2683	2686	2026-03-08 08:52:15.227437+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	pending	\N	\N
2702	2705	2026-03-08 11:05:54.46033+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2707	2710	2026-03-08 11:05:54.477464+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2708	2711	2026-03-08 11:05:54.4808+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2709	2712	2026-03-08 11:05:54.483957+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2711	2714	2026-03-08 11:05:54.490294+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2712	2715	2026-03-08 11:05:54.493499+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2715	2718	2026-03-08 11:05:54.503183+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2716	2719	2026-03-08 11:07:26.19559+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2717	2720	2026-03-08 11:07:26.205159+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2718	2721	2026-03-08 11:07:26.207523+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2719	2722	2026-03-08 11:07:26.20972+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2720	2723	2026-03-08 11:07:26.211877+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	8	2048	pending	\N	\N
2721	2724	2026-03-08 11:07:26.213963+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	8	2048	pending	\N	\N
2722	2725	2026-03-08 11:07:26.216055+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	pending	\N	\N
2724	2727	2026-03-08 11:07:26.348392+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	pending	\N	\N
2723	2726	2026-03-08 11:07:26.345967+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	8757.829511642456
2480	2483	2026-03-04 08:59:45.663309+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2481	2484	2026-03-04 08:59:45.666662+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2483	2486	2026-03-04 08:59:45.673551+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2484	2487	2026-03-04 08:59:45.676142+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2488	2491	2026-03-04 08:59:45.814191+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2489	2492	2026-03-04 08:59:45.816582+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2490	2493	2026-03-04 08:59:45.818968+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2491	2494	2026-03-04 08:59:45.821362+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2492	2495	2026-03-04 08:59:45.823702+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2503	2506	2026-03-04 08:59:45.849587+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2496	2499	2026-03-04 08:59:45.833098+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2504	2507	2026-03-04 08:59:45.851871+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2505	2508	2026-03-04 08:59:45.854153+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2509	2512	2026-03-04 08:59:45.863507+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2506	2509	2026-03-04 08:59:45.856398+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2514	2517	2026-03-04 08:59:45.875176+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2515	2518	2026-03-04 08:59:45.877476+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2516	2519	2026-03-04 08:59:45.879814+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2517	2520	2026-03-04 08:59:45.882105+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	1	2048	completed	\N	0
2521	2524	2026-03-04 08:59:45.891447+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2522	2525	2026-03-04 08:59:45.947167+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	98.1319637298584
2523	2526	2026-03-04 08:59:45.950478+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	221.3960087299347
2524	2527	2026-03-04 08:59:45.953047+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	413.632848739624
2513	2516	2026-03-04 08:59:45.872835+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2525	2528	2026-03-04 08:59:45.955512+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	661.7998061180115
2531	2534	2026-03-04 08:59:45.969448+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	80.73060536384583
2532	2535	2026-03-04 08:59:45.971729+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	245.67249464988708
2533	2536	2026-03-04 08:59:45.974054+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	380.43013548851013
2527	2530	2026-03-04 08:59:45.960247+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1514.085679769516
2534	2537	2026-03-04 08:59:45.976414+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	699.153813123703
2535	2538	2026-03-04 08:59:45.978704+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1014.0882225036621
2539	2542	2026-03-04 08:59:45.987946+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.0019893646240234375
2541	2544	2026-03-04 08:59:45.992621+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.0031003952026367188
2542	2545	2026-03-04 08:59:45.994937+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.003847360610961914
2543	2546	2026-03-04 08:59:45.997202+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.004045009613037109
2544	2547	2026-03-04 08:59:45.999454+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.004546403884887695
2547	2550	2026-03-04 08:59:46.006409+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	215.13148474693298
2548	2551	2026-03-04 08:59:46.008738+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	214.21550011634827
2549	2552	2026-03-04 08:59:46.011054+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	299.237154006958
2550	2553	2026-03-04 08:59:46.013351+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	562.0330393314362
2510	2513	2026-03-04 08:59:45.865856+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2558	2561	2026-03-04 08:59:46.032007+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	2667.689192533493
2559	2562	2026-03-04 08:59:46.034385+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	2344.516577720642
2560	2563	2026-03-04 08:59:46.036806+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	2519.0365483760834
2508	2511	2026-03-04 08:59:45.861015+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2536	2539	2026-03-04 08:59:45.981017+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1222.2413864135742
2564	2567	2026-03-04 08:59:46.046254+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	337.50966787338257
2568	2571	2026-03-04 08:59:46.055737+00	rtn	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0.004019498825073242
2567	2570	2026-03-04 08:59:46.053394+00	gptq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	538.1503298282623
2566	2569	2026-03-04 08:59:46.050994+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	8563.205201387405
2571	2574	2026-03-04 08:59:46.062897+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	8627.199874639511
2569	2572	2026-03-04 08:59:46.058088+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	11270.243388175964
2572	2575	2026-03-04 08:59:46.065301+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	11421.6764793396
2580	2583	2026-03-04 08:59:46.085614+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0020112991333007812
2581	2584	2026-03-04 08:59:46.088016+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.004071474075317383
2582	2585	2026-03-04 08:59:46.090556+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0038177967071533203
2583	2586	2026-03-04 08:59:46.093196+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0037517547607421875
2584	2587	2026-03-04 08:59:46.095653+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	c4	0	2048	completed	\N	0.0046024322509765625
2585	2588	2026-03-04 08:59:46.098987+00	gptq	\N	2	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	819.6254007816315
2575	2578	2026-03-04 08:59:46.072709+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	8586.806712150574
2578	2581	2026-03-04 08:59:46.080629+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	4972.95735502243
2626	2629	2026-03-05 08:40:18.21783+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0
2630	2633	2026-03-05 08:40:18.235717+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2631	2634	2026-03-05 08:40:18.238184+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2632	2635	2026-03-05 08:40:18.240541+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2633	2636	2026-03-05 08:40:18.369158+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2634	2637	2026-03-05 08:40:18.371752+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0
2637	2640	2026-03-05 08:40:18.378974+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2638	2641	2026-03-05 08:40:18.38129+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2639	2642	2026-03-05 08:40:18.383664+00	rtn	\N	16	t	t	\N	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	0
2642	2645	2026-03-05 08:40:18.390479+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1706.24693775177
2643	2646	2026-03-05 08:40:18.392701+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	3427.9066722393036
2645	2648	2026-03-05 08:40:18.401867+00	gptq	\N	3	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	1693.7398233413696
2647	2650	2026-03-05 08:40:18.406518+00	rtn	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	0.005620479583740234
2649	2652	2026-03-05 08:40:18.410989+00	gptq	\N	4	t	f	\N	f	\N	f	\N	0	\N	{}	c4	128	2048	completed	\N	454.7632055282593
2653	2656	2026-03-05 08:40:18.420071+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	747.3883266448975
2654	2657	2026-03-05 08:40:18.422304+00	llmint8	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	0.005609035491943359
2655	2658	2026-03-05 08:40:18.424547+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	287.5582308769226
2659	2662	2026-03-05 08:40:18.433658+00	smoothquant	\N	8	t	t	\N	f	\N	f	\N	0	\N	{}	pile	512	2048	completed	\N	889.0016098022461
2661	2664	2026-03-05 08:40:18.438226+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	17854.828986167908
2662	2665	2026-03-05 08:40:18.440446+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	26154.748739480972
2663	2666	2026-03-05 08:40:18.442661+00	awq	\N	3	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	10690.586141347885
2665	2668	2026-03-05 08:40:18.447101+00	awq	\N	4	t	f	128	f	\N	f	\N	0	\N	{}	pile	16	2048	completed	\N	6385.599173307419
\.


--
-- Data for Name: scientist_reports; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.scientist_reports (id, experiment_id, created_at, llm_model, llm_provider, prompt_payload_json, report_markdown, summary, pass_fail, confidence_score, reasoning_tags, key_findings, suggested_experiments, prompt_tokens, completion_tokens, total_tokens, extra_metadata) FROM stdin;
\.


--
-- Data for Name: wandb_sync_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.wandb_sync_log (id, experiment_id, sync_direction, sync_type, synced_at, status, details) FROM stdin;
\.


--
-- Name: calibration_records_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.calibration_records_id_seq', 1, false);


--
-- Name: environment_snapshots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.environment_snapshots_id_seq', 1, false);


--
-- Name: experiment_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.experiment_groups_id_seq', 1, false);


--
-- Name: experiments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.experiments_id_seq', 2727, true);


--
-- Name: hardware_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.hardware_stats_id_seq', 1, false);


--
-- Name: knowledge_edges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.knowledge_edges_id_seq', 291, true);


--
-- Name: layer_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.layer_metrics_id_seq', 1, false);


--
-- Name: metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metrics_id_seq', 675, true);


--
-- Name: paper_notes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.paper_notes_id_seq', 1, false);


--
-- Name: quant_configs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.quant_configs_id_seq', 2724, true);


--
-- Name: scientist_reports_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.scientist_reports_id_seq', 1, false);


--
-- Name: wandb_sync_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.wandb_sync_log_id_seq', 1, false);


--
-- Name: calibration_records calibration_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calibration_records
    ADD CONSTRAINT calibration_records_pkey PRIMARY KEY (id);


--
-- Name: environment_snapshots environment_snapshots_env_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environment_snapshots
    ADD CONSTRAINT environment_snapshots_env_hash_key UNIQUE (env_hash);


--
-- Name: environment_snapshots environment_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.environment_snapshots
    ADD CONSTRAINT environment_snapshots_pkey PRIMARY KEY (id);


--
-- Name: experiment_groups experiment_groups_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiment_groups
    ADD CONSTRAINT experiment_groups_name_key UNIQUE (name);


--
-- Name: experiment_groups experiment_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiment_groups
    ADD CONSTRAINT experiment_groups_pkey PRIMARY KEY (id);


--
-- Name: experiments experiments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiments
    ADD CONSTRAINT experiments_pkey PRIMARY KEY (id);


--
-- Name: experiments experiments_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiments
    ADD CONSTRAINT experiments_uuid_key UNIQUE (uuid);


--
-- Name: hardware_stats hardware_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hardware_stats
    ADD CONSTRAINT hardware_stats_pkey PRIMARY KEY (id);


--
-- Name: knowledge_edges knowledge_edges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_edges
    ADD CONSTRAINT knowledge_edges_pkey PRIMARY KEY (id);


--
-- Name: knowledge_edges knowledge_edges_source_id_target_id_edge_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_edges
    ADD CONSTRAINT knowledge_edges_source_id_target_id_edge_type_key UNIQUE (source_id, target_id, edge_type);


--
-- Name: knowledge_nodes knowledge_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_nodes
    ADD CONSTRAINT knowledge_nodes_pkey PRIMARY KEY (id);


--
-- Name: layer_metrics layer_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layer_metrics
    ADD CONSTRAINT layer_metrics_pkey PRIMARY KEY (id);


--
-- Name: metrics metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrics
    ADD CONSTRAINT metrics_pkey PRIMARY KEY (id);


--
-- Name: paper_notes paper_notes_paper_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_notes
    ADD CONSTRAINT paper_notes_paper_id_key UNIQUE (paper_id);


--
-- Name: paper_notes paper_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.paper_notes
    ADD CONSTRAINT paper_notes_pkey PRIMARY KEY (id);


--
-- Name: quant_configs quant_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quant_configs
    ADD CONSTRAINT quant_configs_pkey PRIMARY KEY (id);


--
-- Name: scientist_reports scientist_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scientist_reports
    ADD CONSTRAINT scientist_reports_pkey PRIMARY KEY (id);


--
-- Name: wandb_sync_log wandb_sync_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wandb_sync_log
    ADD CONSTRAINT wandb_sync_log_pkey PRIMARY KEY (id);


--
-- Name: idx_calibration_records_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_calibration_records_experiment_id ON public.calibration_records USING btree (experiment_id);


--
-- Name: idx_experiments_config_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_config_hash ON public.experiments USING btree (config_hash);


--
-- Name: idx_experiments_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_created_at ON public.experiments USING btree (created_at DESC);


--
-- Name: idx_experiments_model_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_model_name ON public.experiments USING btree (model_name);


--
-- Name: idx_experiments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_status ON public.experiments USING btree (status);


--
-- Name: idx_experiments_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_tags ON public.experiments USING gin (tags);


--
-- Name: idx_experiments_wandb_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_wandb_run_id ON public.experiments USING btree (wandb_run_id);


--
-- Name: idx_hardware_stats_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hardware_stats_experiment_id ON public.hardware_stats USING btree (experiment_id);


--
-- Name: idx_hardware_stats_quant_config_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hardware_stats_quant_config_id ON public.hardware_stats USING btree (quant_config_id);


--
-- Name: idx_knowledge_edges_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_knowledge_edges_source ON public.knowledge_edges USING btree (source_id);


--
-- Name: idx_knowledge_edges_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_knowledge_edges_target ON public.knowledge_edges USING btree (target_id);


--
-- Name: idx_knowledge_nodes_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_knowledge_nodes_type ON public.knowledge_nodes USING btree (node_type);


--
-- Name: idx_layer_metrics_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_layer_metrics_experiment_id ON public.layer_metrics USING btree (experiment_id);


--
-- Name: idx_layer_metrics_layer_index; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_layer_metrics_layer_index ON public.layer_metrics USING btree (layer_index);


--
-- Name: idx_layer_metrics_quant_config_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_layer_metrics_quant_config_id ON public.layer_metrics USING btree (quant_config_id);


--
-- Name: idx_layer_metrics_stat_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_layer_metrics_stat_name ON public.layer_metrics USING btree (stat_name);


--
-- Name: idx_metrics_dataset; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_dataset ON public.metrics USING btree (dataset);


--
-- Name: idx_metrics_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_experiment_id ON public.metrics USING btree (experiment_id);


--
-- Name: idx_metrics_metric_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_metric_name ON public.metrics USING btree (metric_name);


--
-- Name: idx_metrics_quant_config_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_quant_config_id ON public.metrics USING btree (quant_config_id);


--
-- Name: idx_paper_notes_method_names; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_paper_notes_method_names ON public.paper_notes USING gin (method_names);


--
-- Name: idx_paper_notes_paper_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_paper_notes_paper_id ON public.paper_notes USING btree (paper_id);


--
-- Name: idx_paper_notes_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_paper_notes_tags ON public.paper_notes USING gin (tags);


--
-- Name: idx_quant_configs_bit_width; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quant_configs_bit_width ON public.quant_configs USING btree (bit_width);


--
-- Name: idx_quant_configs_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quant_configs_experiment_id ON public.quant_configs USING btree (experiment_id);


--
-- Name: idx_quant_configs_method_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quant_configs_method_name ON public.quant_configs USING btree (method_name);


--
-- Name: idx_scientist_reports_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scientist_reports_experiment_id ON public.scientist_reports USING btree (experiment_id);


--
-- Name: idx_scientist_reports_pass_fail; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scientist_reports_pass_fail ON public.scientist_reports USING btree (pass_fail);


--
-- Name: idx_scientist_reports_reasoning_tags; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scientist_reports_reasoning_tags ON public.scientist_reports USING gin (reasoning_tags);


--
-- Name: experiments update_experiments_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_experiments_updated_at BEFORE UPDATE ON public.experiments FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: paper_notes update_paper_notes_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_paper_notes_updated_at BEFORE UPDATE ON public.paper_notes FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: calibration_records calibration_records_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.calibration_records
    ADD CONSTRAINT calibration_records_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: experiments experiments_environment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiments
    ADD CONSTRAINT experiments_environment_id_fkey FOREIGN KEY (environment_id) REFERENCES public.environment_snapshots(id);


--
-- Name: experiments experiments_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.experiments
    ADD CONSTRAINT experiments_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.experiment_groups(id);


--
-- Name: hardware_stats hardware_stats_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hardware_stats
    ADD CONSTRAINT hardware_stats_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: hardware_stats hardware_stats_quant_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hardware_stats
    ADD CONSTRAINT hardware_stats_quant_config_id_fkey FOREIGN KEY (quant_config_id) REFERENCES public.quant_configs(id) ON DELETE CASCADE;


--
-- Name: knowledge_edges knowledge_edges_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_edges
    ADD CONSTRAINT knowledge_edges_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.knowledge_nodes(id);


--
-- Name: knowledge_edges knowledge_edges_target_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.knowledge_edges
    ADD CONSTRAINT knowledge_edges_target_id_fkey FOREIGN KEY (target_id) REFERENCES public.knowledge_nodes(id);


--
-- Name: layer_metrics layer_metrics_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layer_metrics
    ADD CONSTRAINT layer_metrics_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: layer_metrics layer_metrics_quant_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.layer_metrics
    ADD CONSTRAINT layer_metrics_quant_config_id_fkey FOREIGN KEY (quant_config_id) REFERENCES public.quant_configs(id) ON DELETE CASCADE;


--
-- Name: metrics metrics_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrics
    ADD CONSTRAINT metrics_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: metrics metrics_quant_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metrics
    ADD CONSTRAINT metrics_quant_config_id_fkey FOREIGN KEY (quant_config_id) REFERENCES public.quant_configs(id) ON DELETE CASCADE;


--
-- Name: quant_configs quant_configs_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quant_configs
    ADD CONSTRAINT quant_configs_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: quant_configs quant_configs_parent_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quant_configs
    ADD CONSTRAINT quant_configs_parent_config_id_fkey FOREIGN KEY (parent_config_id) REFERENCES public.quant_configs(id);


--
-- Name: scientist_reports scientist_reports_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scientist_reports
    ADD CONSTRAINT scientist_reports_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- Name: wandb_sync_log wandb_sync_log_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wandb_sync_log
    ADD CONSTRAINT wandb_sync_log_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.experiments(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict TOGfl5zJdwRzClCmd3ujMvtFKT06FGH5yO93KA6Ddl5bdQKdUKUcSPgahd2W7KB

