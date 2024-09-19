# -*- coding: utf-8 -*-
"""B.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1m473AZ648KxE2yiWjnhv061RVf2v1HGK
"""

# Commented out IPython magic to ensure Python compatibility.
import shutil
import streamlit as st
st.set_page_config(
   page_title="RAG Configuration",
   page_icon="🤖",
   layout="wide",
   initial_sidebar_state="collapsed"
)
from langchain_openai import ChatOpenAI
import requests
import openai
import multiprocessing
from langchain.document_loaders import TextLoader, JSONLoader
from langchain.docstore.document import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain_openai.embeddings import OpenAIEmbeddings
import weaviate
# from langchain.vectorstores import Weaviate

import weaviate
import asyncio
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from weaviate.embedded import EmbeddedOptions
import os
from pathlib import Path
from pprint import pprint
from sklearn.cluster import DBSCAN
from langchain_community.llms import HuggingFaceHub
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.chat_models import ChatHuggingFace
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from datasets import Dataset
from scipy.spatial.distance import euclidean
from sentence_transformers import CrossEncoder, SentenceTransformer
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
    # context_relevancy,
    answer_correctness,
    answer_similarity
)
from ragas import evaluate
from typing import Sequence, List
from langchain.vectorstores import Pinecone
import pandas as pd
import numpy as np
import json
from pdfminer.high_level import extract_text
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_core.runnables import RunnableLambda
# from pinecone_notebooks.colab import Authenticate
from langchain_weaviate.vectorstores import WeaviateVectorStore
from langchain.text_splitter import *
from langchain.smith import RunEvalConfig
from langchain_core.runnables import chain
from langsmith import Client
import re
from langchain_core.messages import HumanMessage
from langgraph.graph import END, MessageGraph, Graph, StateGraph
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from openai import OpenAI
from transformers import pipeline
import torch
from langchain.retrievers import ContextualCompressionRetriever, MergerRetriever
from langchain_community.document_compressors import LLMLinguaCompressor
from typing_extensions import TypedDict
import dspy
import PyPDF2
# %load_ext autoreload
from dspy.evaluate import Evaluate
from dspy.retrieve.weaviate_rm import WeaviateRM
from dspy.retrieve.pinecone_rm import PineconeRM

os.environ["url"] = st.secrets["url"]
url =st.secrets["url"]
url="https://jevp6yz2q4uet57pzfbfvw.c0.us-west3.gcp.weaviate.cloud"
WEAVIATE_API_KEY=st.secrets["WEAVIATE_API_KEY"]
pinecone_api_key =st.secrets["PINECONE_API_KEY"]
# st.session_state['bi_encoder'] =bi_encoder()
# st.session_state['chat_model'] = chat_model()
# st.session_state['cross_model'] =load_cross()
# st.session_state['q_model'] = q_model()
# st.session_state['extractor'], st.session_state['image_model'] = load_image_model("google/vit-base-patch16-224-in21k")
if 'weaviate_embed' not in st.session_state:
    st.session_state['weaviate_embed'] = None  # You can assign None or a default value

# Safely access 'weaviate_embed' after initializing it
weaviate_embed = st.session_state['weaviate_embed']

# Initialize 'pinecone_embed' in session state if it does not exist
if 'pinecone_embed' not in st.session_state:
    st.session_state['pinecone_embed'] = None  # You can assign None or a default value

# Safely access 'pinecone_embed' after initializing it
pinecone_embed = st.session_state['pinecone_embed']
client = weaviate.connect_to_wcs(
    cluster_url=url,
    auth_credentials=weaviate.classes.init.Auth.api_key(WEAVIATE_API_KEY),
    )

gpt_3_5_turbo = dspy.OpenAI(model="gpt-3.5-turbo",max_tokens=128) # setting up an LLM
dspy.settings.configure(lm=gpt_3_5_turbo, rm=client) # Configuring a global LLM using the 'client' object
class RAG(dspy.Signature):
  """Given a question and its context, output an answer"""
  question = dspy.InputField()
  context = dspy.InputField(desc="list of contexts")
  answer = dspy.OutputField()
answerer = dspy.ChainOfThought(RAG)
class Reranker(dspy.Signature):
  """Given a list of contexts, re-rank them in order of relevance"""
  contexts = dspy.InputField()
  reranked_contexts = dspy.OutputField(desc="not more than 5 contexts")
reranker = dspy.Predict(Reranker)
class Retrieval(dspy.Signature):
  """Given a question, retrieve a list of relevant contexts"""
  question = dspy.InputField()
  contexts = dspy.OutputField()
retrieve = dspy.Retrieve(Retrieval)
class Decider(dspy.Signature):
    print("i come in the decider ")
    """Given a question, determine whether to retrieve or not based on context"""
    question = dspy.InputField(desc="question must be evaluated for retrieval based on the broader context")
    decision = dspy.OutputField(desc="Yes or No")

decider = dspy.Predict(Decider)


def rag_chain(question):
  decision = decider(question=question).decision
  if(decision.lower()=='No'): # OOD Q
    answer = dspy.Predict("question -> answer")(question=question).answer
  else: # Retrieval
    retrieval_response = retrieve(question).passages
    contexts = reranker(contexts=retrieval_response.contexts).reranked_contexts
    answer = answerer(question=question, context=contexts).answer
  return answer
bi_encoder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L12-v2", model_kwargs={"device": "cpu"})
class SentenceTransformerEmbeddings:
  def __init__(self, model_name: str):
      self.model = SentenceTransformer(model_name)

  def embed_documents(self, texts):
      return self.model.encode(texts, convert_to_tensor=True).tolist()

  def embed_query(self, text):
      return self.model.encode(text, convert_to_tensor=True).tolist()
weaviate_embed = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
pinecone_embed = SentenceTransformerEmbeddings(model_name="all-mpnet-base-v2") # 784 dimension + euclidean

cross_encoder = CrossEncoder("cross-encoder/ms-marco-TinyBERT-L-2-v2", max_length=512, device="cpu")
cross_model = RunnableLambda(cross_encoder.predict)
pine_cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2", max_length=512, device="cpu")
weaviate_cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512, device="cpu")

template = """You are an assistant for question-answering tasks.
        Use the following pieces of retrieved context to answer the question.
        If you don't know the answer, just say that you don't know.
        Else, answer as a human being would.
        Use two sentences maximum and keep the answer concise.
        Question: {question}
        Context: {context}
        Answer:
        """
chat_model = HuggingFaceHub(
    repo_id="mistralai/Mistral-7B-Instruct-v0.1",
    model_kwargs={"temperature": 0.5, "max_length": 64,"max_new_tokens":512, "query_wrapper_prompt":template}
)

class MistralParser():
  stopword = 'Answer:'

  def __init__(self):
    self.parser = StrOutputParser()

  def invoke(self,query):
    ans = self.parser.invoke(query)

    return ans[ans.find(self.stopword)+len(self.stopword):].strip()
mistral_parser = RunnableLambda(MistralParser().invoke)

class VectorDatabase:
  def __init__(self, embedding_model, cross_encoder, v_type, api_key, **kwargs): # kwargs : index, dimension, metric, url
    self.embedding_model = embedding_model
    self.cross_encoder = cross_encoder
    self.v_type = v_type
    self.extra = {}
    for key,value in kwargs.items():
      self.extra[key] = value

    if(self.v_type=='Pinecone'):
      self.vector_inst = Pinecone(api_key=api_key)
      index_name = self.extra['index']
      existing_indexes = [index_info["name"] for index_info in self.vector_inst.list_indexes()]

      if index_name not in existing_indexes:
          self.vector_inst.create_index(
              name=index_name,
              dimension=self.extra['dimension'],
              metric=self.extra['metric'],
              spec=ServerlessSpec(cloud="aws", region="us-east-1"),
          )
    else:
      self.vector_inst = weaviate.connect_to_wcs(cluster_url=self.extra['url'],auth_credentials=weaviate.classes.init.Auth.api_key(api_key))

  def data_prep(self,data,splitter):
    documents = [Document(page_content=data)]
    text_splitter = splitter
    chunks = text_splitter.split_documents(documents)
    return chunks

  def upsert(self,data,splitter):
    chunks = self.data_prep(data,splitter)
    if(self.v_type=='Pinecone'):
      self.retriever = PineconeVectorStore.from_documents(chunks, self.embedding_model, index_name=self.extra['index']).as_retriever(search_type='similarity')
    else:
      self.retriever = WeaviateVectorStore.from_documents(chunks, self.embedding_model, client=self.vector_inst).as_retriever(search_type="mmr")

  def query(self,question):
    if self.v_type=='Pinecone':
      context = [doc.page_content for doc in self.retriever.invoke(question)]
      print(f"Pinecone retrieved : {len(context)}")
    else:
      context = [doc.page_content for doc in self.retriever.invoke(question)]
      print(f"Weaviate retrieved : {len(context)}")

    c = self.cross_encoder.rank(
             query=question,
              documents=context,
              return_documents=True
            )[:len(context)-2]
    return [i['text'] for i in c]

pine_vb = VectorDatabase(pinecone_embed, pine_cross_encoder, 'Pinecone', pinecone_api_key, index='rag', dimension=768, metric='euclidean',url=None)

weaviate_vb = VectorDatabase(weaviate_embed, weaviate_cross_encoder, 'Weaviate', WEAVIATE_API_KEY, index=None, dimension=None, metric=None, url=url)

pine_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1330, chunk_overlap=35)
weaviate_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1330, chunk_overlap=35)

vb_list = [
    (pine_vb, pine_text_splitter),
    (weaviate_vb, weaviate_text_splitter)
]

eval_config = RunEvalConfig(evaluators=["qa"])
client = Client()

openAIClient = OpenAI(api_key="sk-proj-PMJ67akceG4mbeOTbBJVT3BlbkFJvLd9KWYTh4NKefAWfvl8")

class chatGPT:
  def __init__(self,model,api_key, template):
    self.model = model
    openAIClient = OpenAI(api_key=api_key)
    self.template = template

  def chat(self, prompt):
    message = [{"role":"user", "content":prompt.messages[0].content}]
    return openAIClient.chat.completions.create(messages=message, model=self.model).choices[0].message.content


gpt_4o = chatGPT('gpt-4o', os.environ.get("OPENAI_API_KEY"), template)
gpt_model = RunnableLambda(gpt_4o.chat)

gq_model = RunnableLambda(chatGPT('gpt-3.5-turbo', os.environ.get("OPENAI_API_KEY"), template).chat)

prompt = """
        You run in a loop of Thought, Action, PAUSE, Observation.
        At the end of the loop you output an Answer.
        You will be provided with a question, which you have to answer in the following manner:

        You will break the question in a series of subquestions, each one building up on the previous one.
        Each subquestion has to be answered as:

        Thought: A <sub-question> based on the <asked-question>.
        Action: FETCH <sub-question>
        PAUSE
        Observation: List of context regarding the <sub-question> which will be provided to you

        You will formulate the next sub question based on this observation
        You will continue to do so till you have all of the relevant context required for the initial question to be answered.

        Your Output:
        Answer: List of context for <asked-question>

        Description of action FETCH:
        given a question, it will fetch relevant context from vector databases

        Example session:

        Question:

        Thought:
        Action:
        PAUSE
        Observation:

        Thought:
        Action:
        PAUSE
        Observation:

        Your Output:
        Answer:
        """.strip()

prompt = """
        You will be given a pair of question and its context as an input.
        You must form a question contextually related to both of them.
        Format for input:
        Question : <Question>
        Context: <Context>

        Format for output:
        Output: <Output>
        """.strip()
q_model = HuggingFaceHub(
    repo_id="mistralai/Mistral-7B-Instruct-v0.1",
    model_kwargs={"temperature": 0.5, "max_length": 64,"max_new_tokens":512}
)


class QueryAgent:
    max_turns = 3
    best = 2
    prompt = """
        You will be given a pair of question and its context as an input.
        You must form a question contextually related to both of them.
        Format for input:
        Question : <Question>
        Context: <Context>

        Format for output:
        Output: <Output>
        """.strip()

    def __init__(self,vb_list, q_model, cross_model, parser=RunnableLambda(lambda x: x)):
        self.vb_list = vb_list
        self.q_model = q_model
        self.cross_model = cross_model
        self.parser = parser
        self.messages = [{"role": "system", "content": self.prompt}]

    def __call__(self, query, context):
        message = f"Question: {query}\nContext: {context}"
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result

    def fetch(self,question):
      prior_context = [vb.query(question) for vb,_ in self.vb_list]
      cont = ["".join(i) for i in prior_context]
      c = self.cross_model.rank(
            query=question,
            documents=cont,
            return_documents=True
          )[:len(cont)-self.best+1]
      return [i['text'] for i in c]

    def execute(self):
      content = "\n".join([message["content"] for message in self.messages if(message["role"]!="assistant")])
      return self.parser.invoke(self.q_model.invoke(content, max_length=128, num_return_sequences=1))

    def query(self,question):
      self.question = question
      self.context,context = "",""

      for i in range(self.max_turns):
        self.context += context + '@@'
        subq = self(question,context)
        print(f"Sub question: {subq}\n")
        question, context = subq, "".join(self.fetch(subq))
        print(f"Context: {context}\n")
      return self.context

q_parser = RunnableLambda(lambda ans: ans.split('\n')[-1].strip()[len('Output: '):])

query_agent = RunnableLambda(QueryAgent(vb_list, q_model,cross_encoder, q_parser).query)

class AugmentedQueryAgent: #HyDE
  best = 2

  def __init__(self,vb_list,model,cross_model=cross_encoder, parser=RunnableLambda(lambda x: x)):
    self.system = "You are a helpful assistant. Provide an example answer to the given question that may be found in a manual."
    self.model = model
    self.vb_list = vb_list
    self.cross_model = cross_model
    self.parser = parser
    self.messages = [{"role": "system","content": self.system}]

  def fetch(self,question):
    prior_context = [vb.query(question) for vb,_ in self.vb_list]
    cont = ["".join(i) for i in prior_context]
    c = self.cross_model.rank(
          query=question,
          documents=cont,
          return_documents=True
        )[:len(cont)-self.best+1]
    return [i['text'] for i in c]

  def query(self,question):
    self.messages.append({"role":"user","content":question})
    content = "\n".join([message["content"] for message in self.messages if(message["role"]!="assistant")])
    con = self.fetch(self.parser.invoke(self.model.invoke(content, max_length=128, num_return_sequences=1)))
    context = ""
    for i in con:
      context += i + "@@"
    return context

aq_parser = RunnableLambda(lambda ans: ("".join(ans.split('\n')[1:])).strip())

# vb_list,model,cross_model=cross_encoder, parser=RunnableLambda(lambda x: x)
agq = RunnableLambda(AugmentedQueryAgent(vb_list, q_model, cross_encoder, parser=aq_parser).query)

class SubQueryAgent:
  best = 2
  turns = 3

  class QueryGen:
    def __init__(self, q_model, parser=RunnableLambda(lambda x: x), prompt="""
        You will be given a pair of question and its context as an input.You must form a question contextually related to both of them.
        Question : {Question}\nContext: {Context}
        Output should in the format: sub-question : <sub_question>"""):
      self.context = ""
      self.prompt = ChatPromptTemplate.from_template(prompt.strip())
      self.chain = {"Question":RunnablePassthrough(), "Context":RunnableLambda(lambda c: self.context)} | self.prompt | q_model | parser

    def __call__(self, question, context=""):
      self.context = context
      return self.chain.invoke(question)

  def __init__(self,vb_list,q_model, cross_model, parser=RunnableLambda(lambda x: x)):
    self.vb_list = vb_list
    self.q_model = q_model
    self.parser = parser
    self.cross_model = cross_model

  def fetch(self,question):
    prior_context = [vb.query(question) for vb,_ in self.vb_list]
    cont = []
    for i in prior_context:
      context = ""
      for j in i: # list to str
        context += j
      cont.append(context)

    c = self.cross_model.rank(
          query=question,
          documents=cont,
          return_documents=True
        )[:len(prior_context)-self.best+1]
    return [i['text'] for i in c] # list of text

  def query(self,question):
    agent = self.QueryGen(self.q_model, self.parser)
    sub_q = agent(question)
    print(f"Sub question: {sub_q}\n")

    contexts = []
    prompt = f"""You are given a main Question {question} and a pair of its subquestion and related sub context.
    You must generate a question based on the main question, and all of the sub-question and sub-contexts pairs.
    Output should in the format: sub-question : <sub_question>"""
    for i in range(self.turns-1):
      print(f"ITERATION NO: {i}")
      context = self.fetch(sub_q)
      contexts += context
      prompt += "\nsub-question : {Question}\nsub-context: {Context}"
      agent = self.QueryGen(self.q_model, self.parser, prompt=prompt)
      sub_q = agent(sub_q, context)
      print(f"Sub question: {sub_q}\n")
    uni = []
    for c in contexts:
      if c not in uni:
        uni.append(c)
    return "@@".join(uni)
sq_agent = RunnableLambda(SubQueryAgent(vb_list, gq_model, cross_encoder).query)

class AlternateQuestionAgent:
  best = 2

  def __init__(self,vb_list,agent, cross_model=cross_encoder, parser=StrOutputParser()):
    self.prompt = ChatPromptTemplate.from_template(
      template="""You are given a question {question}.
      Based on it, you must only generate two alternate questions separated by newlines and numbered which are related to the given question.""",
    )
    self.model = agent
    self.parser = parser
    self.vb_list = vb_list
    self.cross_model = cross_model
    self.chain = {"question":RunnablePassthrough()} | self.prompt | self.model | self.parser

  def mul_qs(self,question):
    qs = [i[3:] for i in (self.chain.invoke(question)).split('\n')] + [question]
    if '' in qs:
      qs.remove('')
    uni_q = []
    for q in qs:
      if q not in uni_q:
        uni_q.append(q)
    return uni_q # assuming the questions are labelled as 1. q1 \n 2. q2

  def query(self, question):
    questions = self.mul_qs(question)
    return self.fetch(questions)

  def fetch(self,questions):
    def retrieve(question):
      prior_context = [vb.query(question) for vb,_ in self.vb_list]
      cont = []
      for i in prior_context:
        context = ""
        for j in i: # list to str
          context += j
        cont.append(context)

      c = self.cross_model.rank(
            query=question,
            documents=cont,
            return_documents=True
          )[:len(prior_context)-self.best+1]
      return [i['text'] for i in c] # list of text

    contexts = [self.retrieve(q) for q in questions]
    uni_contexts = []
    for i in contexts:
      for j in i:
        if j not in uni_contexts:
          uni_contexts.append(j)
    u = []
    for i in uni_contexts:
      k = re.split("(\.|\?|!)\n", i)
      for j in k:
        if j in '.?!':
          continue
        if j not in u:
          u.append(j)
    uni_contexts = []
    for i in range(len(u)):
      for j in range(len(u)):
        if j!=i and u[i] in u[j]:
            break
      else:
        uni_contexts.append(u[i])
    # uni_contexts = u
    contexts = "@@".join(uni_contexts)
    return contexts

aqa_parser = RunnableLambda(lambda x: x[x.find('1. '):])
# vb_list,agent, cross_model=cross_encoder, parser=StrOutputParser()
ag = RunnableLambda(AlternateQuestionAgent(vb_list, q_model, cross_encoder, aqa_parser).query)

def background(f):
  def wrapped(*args, **kwargs):
    return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)
  return wrapped

class TreeOfThoughtAgent:
  def __init__(self,vb_list,model, cross_model, parser=RunnableLambda(lambda x:x)):
    self.alt_agent = RunnableLambda(AlternateQuestionAgent(vb_list, model, cross_model, parser).mul_qs)
    self.sub_agent = RunnableLambda(SubQueryAgent(vb_list, model, cross_model, parser).query)

  def query(self,question):
    contexts = []
    for q in self.alt_agent.invoke(question):
      print(f"Question: {q}")
      contexts.append(self.sub_agent.invoke(q))
    return self.context_clean(contexts)

  def context_clean(self, contexts):
    uni_contexts = []
    for i in contexts:
        if i not in uni_contexts:
          uni_contexts.append(i)
    u = []
    for i in uni_contexts:
      k = re.split("(\.|\?|!)\n", i)
      for j in k:
        if j in '.?!':
          continue
        if j not in u:
          u.append(j)
    uni_contexts = []
    for i in range(len(u)):
      for j in range(len(u)):
        if j!=i and u[i] in u[j]:
            break
      else:
        uni_contexts.append(u[i])
    # uni_contexts = u
    return "@@".join(uni_contexts)


tot_agent = RunnableLambda(TreeOfThoughtAgent(vb_list, gq_model, cross_encoder).query)

class Thresholder:
  upper_limit = 0.8
  lower_limit = 0.4

  def __init__(self, question):
    self.question = question

  def calc(self,context):
    self.context = context
    dataset = Dataset.from_dict({
              "question": self.question,
              "contexts": self.context,
              })
    results = ContextRelevancy().score(dataset)
    return (results<self.lower_limit,results>self.upper_limit,context)


# client = OpenAI(api_key = os.getenv('OPENAI_API_KEY'))
embeddings = OpenAIEmbeddings(model='text-embedding-3-large')

class FeedbackSystem:
  top_k = 1
  def __init__(self, pdf_file, embeddings, url, api):
    self.embeddings = embeddings
    with open(pdf_file) as f:
      data = f.readlines()
    feedback_url = url
    feedback_weaviate_api_key = api
    feedback_vb = weaviate.connect_to_wcs(cluster_url=feedback_url,auth_credentials=weaviate.classes.init.Auth.api_key(feedback_weaviate_api_key))
    self.db = WeaviateVectorStore.from_documents([Document(i) for i in data],embeddings,client=feedback_vb)

  def feedback_retriever(self,top_k=1):
    self.top_k = top_k
    self.retriever = self.db.as_retriever(search_type="mmr", search_kwargs={'k': self.top_k})

  def fetch(self, question, top_k=1):
    self.feedback_retriever(top_k)
    data = self.retriever.invoke(question)
    return [i.page_content for i in data][:top_k]

  def write(self,feedback):
    self.db.add_documents([Document(feedback)])
    self.feedback_retriever(self.top_k)

fs = FeedbackSystem('feedback_loop.txt', embeddings, 'https://jevp6yz2q4uet57pzfbfvw.c0.us-west3.gcp.weaviate.cloud', 'mr8JZynXMHa7qAQ2aXE1JNSfky8X9pjeaW0Z')


def heatmap_gen(question, num=5):
  con = ag.invoke(question)
  chunks = [
      CharacterTextSplitter(
        separator="\n",
        chunk_size=len(c)/(num-1),
        chunk_overlap=0,
        length_function=len,
        is_separator_regex=False
      ).create_documents([c])
      for c in con
  ]
  n = np.ones((len(chunks),len(chunks)))
  for i in range(len(chunks)):
    for j in range(len(chunks)):
      if i!=j:
        n[i,j] = np.average([
            np.array(weaviate_embed.embed_query(chunks[i][k].page_content)).dot(
            np.array(weaviate_embed.embed_query(chunks[j][k].page_content))
            )
            for k in range(len(chunks[i]))
            ]
        )
  return n



# Function to extract text from PDF
def read_pdf(pdf_file):                  #this is the one change i have done here
    try:
        # Open the PDF file
        with open(pdf_file, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            pdf_text = ""

            # Extract text from each page
            for page in reader.pages:
                pdf_text += page.extract_text()

        # Assuming vb_list contains tuples of (vb, sp)
        for vb, sp in vb_list:
            # Ensure `data` is defined properly (in this case, it could be the extracted text)
            data = pdf_text
            vb.upsert(data, sp)

        return vb_list
    except Exception as e:
        print(f"Error reading or processing the PDF: {e}")
        return None


class RAGEval:
    '''
    WorkFlow:
    1. Call RAGEval()
    2. Call ground_truth_prep()
    3. Call model_prep()
    4. Call query()
    5. Call raga()
    '''
    best = 2
    parse = StrOutputParser()

    def __init__(self, vb_list, cross_model): #, q_model, q_parser, q_choice=1): # vb_list = [(vb,splitter)]
        self.cross_model = cross_model

        self.template = """You are an assistant for question-answering tasks.
        Use the following pieces of retrieved context to answer the question.
        If you don't know the answer, just say that you don't know.
        Else, answer as a human being would.
        Use three sentences maximum and keep the answer concise and some times give detail answer.
        Question: {question}
        Context: {context}
        Answer:
        """
        self.prompt = ChatPromptTemplate.from_template(template)
        self.vb_list = vb_list

    def ground_truths_prep(self,questions): # questions is a file with questions
        self.ground_truths = [[s] for s in self.query(questions)]

    def model_prep(self,model,parser_choice=parse): # model_link is the link to the model
        self.chat_model = model
        self.parser = parser_choice

    def query_agent_prep(self,model,parser=parse):
        # self.query_agent = RunnableLambda(QueryAgent(self.vb_list, model,self.cross_model, parser).query)
        # self.query_agent = RunnableLambda(AlternateQuestionAgent(self.vb_list,model,self.cross_model,parser).query)
        self.query_agent = RunnableLambda(TreeOfThoughtAgent(self.vb_list,model,self.cross_model,parser).query)
        # self.query_agent = RunnableLambda(AugmentedQueryAgent(self.vb_list, model,self.cross_model,parser).query)

    def feedback_prep(self, file, embedding, url, api):
      self.fs = FeedbackSystem(file, embedding, url, api)

    def context_prep(self):
      con = self.query_agent.invoke(self.question).split('@@')
      uni_con = []
      for i in con:
        if i not in uni_con:
          uni_con.append(i)

      c = self.cross_model.rank(
                query=self.question,
                documents=uni_con,
                return_documents=True
              )[:self.best]
      self.context = str("\n".join([i['text'] for i in c]))

    def rag_chain(self):
        self.context_prep()
        context_agent = RunnableLambda(lambda x: self.context)
        self.ragchain=(
            {"context":context_agent, "question":RunnablePassthrough()}
                  | self.prompt
                  | self.chat_model
                  | self.parser
        )

    def rag_graph(self):
        class GraphState(TypedDict):

            """
            Represents the state of our graph.

            Attributes:
                question: question
                context: context
                answer: answer
            """
            question: str
            context: str
            answer: str

        self.fs.feedback_retriever(top_k = 1)
        # state : question, context, answer

        def feedback(state):
          datas = self.fs.retriever.invoke(state["question"])
          data = (datas[0]).page_content
          answer = data[data.find('and the response is')+len('and the response is'):]
          self.context = ""
          return {"question":state["question"], "context":self.context, "answer":answer}

        def feedback_check(state): # state modifier
          datas = self.fs.retriever.invoke(state["question"])
          data = (datas[0]).page_content
          q = data[len('The feedback for'):]
          q = q[:q.find('and the response is')].strip()
          q = ((" ".join(q.split(' ')[:-3])).lower()).strip()
          print(f'Feedback Question is {q}')
          if q == (state["question"].lower()).strip():
            return "f_answer"
          else:
            return "fetch"

        def fetch(state): # state modifier
          self.context_prep()
          return {"question":state["question"], "context":self.context, "answer":""}

        def answer(state): # state modifier
          chain = {"context":RunnableLambda(lambda x: state["context"]),"question":RunnablePassthrough()} | self.prompt | self.chat_model | self.parser
          ans = chain.invoke(state["question"])
          return {"question":state["question"],"context":state["context"], "answer":ans}

        def feedback_answer(state):
          template = """
          You are an assistant for question-answering tasks. You are given a question and its answer in a short form. Eloborate the answer till 2 sentences.
          Question: {question}
          Answer: {answer}
          """
          prompt = ChatPromptTemplate.from_template(template)
          chain = {"question":RunnablePassthrough(),"answer":RunnableLambda(lambda x: state["answer"])} | prompt | self.chat_model | self.parser
          return {"question":state["question"],"context":state["context"], "answer":chain.invoke(state["question"])}

        self.RAGraph = StateGraph(GraphState)
        self.RAGraph.set_entry_point("entry")
        self.RAGraph.add_node("entry",RunnablePassthrough())
        self.RAGraph.add_node("feedback", feedback)
        self.RAGraph.add_node("fetch", fetch)
        self.RAGraph.add_node("answerer", answer)
        #self.RAGraph.add_node("f_answer", feedback_answer)
        self.RAGraph.add_edge("entry","feedback")
        self.RAGraph.add_conditional_edges(
            "feedback",
            feedback_check,
            {"f_answer":END, "fetch":"fetch"}
        )
        #self.RAGraph.add_edge("f_answer", END)
        self.RAGraph.add_edge("fetch","answerer")
        self.RAGraph.add_edge("answerer",END)
        self.ragchain = self.RAGraph.compile()

    def query(self,question):
        print(f"MAIN QUESTION {question}")
        self.question = question
        state = {"question":self.question, "context":"", "answer":""}
        self.rag_graph()
        answer_state = self.ragchain.invoke(state)
        req.answer = answer_state["answer"]
        return req.answer

    def ragas(self):
        data = {
            "question": [self.question],
            "answer": [self.answer],
            "contexts": [[self.context]],
            "ground_truth": [self.ground_truth]
        }
        dataset=Dataset.from_dict(data)
        result=evaluate(
            dataset=dataset,
            metrics=[
                context_precision,
                context_recall,
                faithfulness,
                answer_relevancy
            ]
        )
        df=result.to_pandas()
        return df
req = RAGEval(vb_list, cross_encoder)
req.model_prep(gpt_model) #, mistral_parser) # model details
q_parser = RunnableLambda(lambda ans: ans.split('\n')[-1].strip()[len('Output: '):])
alt_parser = RunnableLambda(lambda x: x[x.find('1. '):])
aug_parser = RunnableLambda(lambda ans: ("".join(ans.split('\n')[1:])).strip())

req.query_agent_prep(gq_model) #, parser=alt_parser)

req.feedback_prep('feedback_loop.txt', OpenAIEmbeddings(model='text-embedding-3-large'), 'https://jevp6yz2q4uet57pzfbfvw.c0.us-west3.gcp.weaviate.cloud', 'mr8JZynXMHa7qAQ2aXE1JNSfky8X9pjeaW0Z') # file, embedding, url, api):

req.query_agent_prep(q_model, parser=RunnableLambda(lambda ans: ("".join(ans.split('\n')[1:])).strip()))

req.query_agent_prep(q_model, parser=RunnableLambda(lambda x: x[x.find('1. '):]))

# pinecone_embed = st.session_state['pinecone_embed']
# weaviate_embed = st.session_state['weaviate_embed']
if 'weaviate_embed' not in st.session_state:
    st.session_state['weaviate_embed'] = None  # You can assign None or a default value

# Safely access 'weaviate_embed' after initializing it
weaviate_embed = st.session_state['weaviate_embed']

# Initialize 'pinecone_embed' in session state if it does not exist
if 'pinecone_embed' not in st.session_state:
    st.session_state['pinecone_embed'] = None  # You can assign None or a default value

# Safely access 'pinecone_embed' after initializing it
pinecone_embed = st.session_state['pinecone_embed']

os.environ["HUGGINGFACEHUB_API_TOKEN"] = st.secrets["HUGGINGFACEHUB_API_TOKEN"]
os.environ["LANGCHAIN_PROJECT"] = st.secrets["LANGCHAIN_PROJECT"]
os.environ["OPENAI_API_KEY"] = st.secrets["GPT_KEY"]

st.session_state['pdf_file'] = []
st.session_state['vb_list'] = []
# st.session_state['Settings.embed_model'] = settings()
# st.session_state['processor'], st.session_state['vision_model'] = load_nomic_model()
st.session_state['bi_encoder'] = bi_encoder
st.session_state['chat_model'] = chat_model
st.session_state['cross_model'] = cross_model
st.session_state['q_model'] = q_model
# st.session_state['extractor'], st.session_state['image_model'] = load_image_model("google/vit-base-patch16-224-in21k")
# st.session_state['pinecone_embed'] = pine_embedding_model()
# st.session_state['weaviate_embed'] = weaviate_embedding_model()
os.environ["LANGCHAIN_ENDPOINT"] =st.secrets["LANGCHAIN_ENDPOINT"]
os.environ["LANGCHAIN_API_KEY"] =st.secrets["LANGCHAIN_API_KEY"]  # Update with your API key
os.environ["OPENAI_API_KEY"] =st.secrets["OPENAI_API_KEY"]
#os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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"
os.environ["HUGGINGFACEHUB_API_TOKEN"] =st.secrets["HUGGINGFACEHUB_API_TOKEN"]
os.environ["HF_TOKEN"] =st.secrets["HF_TOKEN"]
os.environ["PINECONE_API_KEY"] =st.secrets["PINECONE_API_KEY"]
os.environ["url"] =st.secrets["url"]
WEAVIATE_API_KEY=st.secrets["WEAVIATE_API_KEY"]
pinecone_api_key = os.environ.get("PINECONE_API_KEY")
# st.session_state['pinecone_embed'] = pine_embedding_model()
# st.session_state['weaviate_embed'] = weaviate_embedding_model()
# pinecone_embed = st.session_state['pinecone_embed']
# weaviate_embed = st.session_state['weaviate_embed']
os.environ["HUGGINGFACE_API_TOKEN"] =st.secrets["HUGGINGFACE_API_TOKEN"]
st.session_state['bi_encoder'] =bi_encoder
st.session_state['chat_model'] = chat_model
st.session_state['cross_model'] =cross_model
st.session_state['q_model'] = q_model

st.title('Multi-modal RAG based LLM for Information Retrieval')
st.subheader('Converse with our Chatbot')
st.markdown('Enter a pdf file as a source.')
uploaded_file = st.file_uploader("Choose an pdf document...", type=["pdf"], accept_multiple_files=False)
if uploaded_file is not None:
    with open(uploaded_file.name, mode='wb') as w:
        print("i ma here")
        w.write(uploaded_file.getvalue())
    if not os.path.exists(os.path.join(os.getcwd(), 'pdfs')):
        os.makedirs(os.path.join(os.getcwd(), 'pdfs'))
    shutil.move(uploaded_file.name, os.path.join(os.getcwd(), 'pdfs'))
    st.session_state['pdf_file'] = uploaded_file.name
    with st.spinner('Extracting'):
        vb_list = read_pdf(pdf_file)    #this is the another change i have done here
    st.session_state['vb_list'] = vb_list
    question = st.text_input("Enter your question:", "how names are present in the context?")

    if st.button("Submit Question"):
        # Step 3: Display the answer to the question
        with st.spinner('Fetching the answer...'):
            # Fetch the answer using the query function
            answer = query(question)
            st.success(f"Answer: {answer}")
    # st.switch_page('pages/rag.py')
