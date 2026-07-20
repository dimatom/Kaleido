import unittest
import langchain
import langchain_core
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

import os
from Kaleido.environment import get_env
from rag_app.rag_core import RAGCore
from Kaleido.logger import logger



class MyTestCase(unittest.TestCase):
    def test_llm(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("你是一名生活小助手"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        client = ChatOpenAI(
            base_url=get_env(
                "KALEIDO_LLM_BASE_URL",
                aliases=("Kaleido_BASE_URL",),
            ),
            api_key=get_env(
                "KALEIDO_LLM_API_KEY",
                aliases=("Kaleido_API_KEY",),
            ),
            model=get_env("KALEIDO_LLM_MODEL", default="deepseek-v4-pro"))

        parser = StrOutputParser()
        chain = prompt | client | parser
        resp = chain.invoke({
            "input": "我早上起来要刷牙、煮鸡蛋、收拾书包、晾衣服，请帮我安排一下这些事情的次序"
        })
        logger.info(resp)

    def test_llm_embeddings(self):
        llm_embeddings = OllamaEmbeddings(
            model=get_env("KALEIDO_EMBEDDING_MODEL", default="qwen3-embedding"),
            base_url=get_env(
                "KALEIDO_EMBEDDING_BASE_URL",
                default="http://127.0.0.1:11434",
            )
        )

        res = llm_embeddings.embed_query(
            "修订后的《保障中小企业款项支付条例》自2025年6月1日起施行。修订后的《条例》明确，机关、事业单位和大型企业不得要求中小企业接受不合理的付款期限、方式、条件和违约责任等交易条件，不得拖欠中小企业的货物、工程、服务款项。机关、事业单位从中小企业采购货物、工程、服务，应当自货物、工程、服务交付之日起30日内支付款项；合同另有约定的，从其约定，但付款期限最长不得超过60日。")
        logger.info(res)

    def test_split_document(self):
        base_url = "C:/Users/lym_d/Desktop/data/"
        #doc_list = self.load_documents(base_url + "生态林业部.docx")
        #doc_list = self.load_documents(base_url + "CPQ.md")
        doc_list = self.load_documents(base_url + "sql.txt")
        #doc_list = self.load_documents(base_url + "接口文档.pdf")
        # doc_list = self.load_documents(base_url + "项目信息.pdf")
        logger.info(doc_list)

    def load_documents(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        try:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith('.docx'):
                loader = Docx2txtLoader(file_path)
            elif file_path.endswith(('.txt', '.md')):
                loader = TextLoader(file_path)
            else:
                logger.info("不支持的文件格式")
                logger.info("支持格式：.pdf, .docx, .txt, .md")
                return None

            documents = loader.load()
            logger.info(f"成功加载文档：{file_path}")
            total_len = sum(len(d.page_content) for d in documents)
            logger.info(f"文档信息：共 {len(documents)} 页/段，总字符数：{total_len}")
            return documents

        except Exception as e:
            logger.info(f"加载文档失败：{str(e)}")
            return None

    def test_db(self):
        rag = RAGCore("test2")
        rag.parse_document(
            [
                {
                    "path": "C:/Users/lym_d/Desktop/data/接口文档.pdf",
                    "metadata": {
                        "document_id": "1"
                    }
                },
                {
                    "path": "C:/Users/lym_d/Desktop/data/项目信息.pdf",
                    "metadata": {
                        "document_id": "2"
                    }
                }
            ]
        )
        res = rag.vectorstore.search("博创项目的日例会会议号是什么？", search_type="similarity")
        logger.info(res)

    def test_search(self):
        rag = RAGCore("test2")
        res = rag.vectorstore.search("随机附件OA审批回传接口的调用方式是什么？", search_type="similarity")
        logger.info(res)

    def test_delete_collection(self):
        rag = RAGCore("test2")
        rag.delete_collection()

    def test_delete_document(self):
        rag = RAGCore("test2")
        rag.delete_document(["1"])

    def test_chain(self):
        rag = RAGCore("test2")
        chain = rag.test_build_chain()
        resp = chain.invoke({
            "input": "博创项目的接口有多少个？请问你的身份是什么？",
            "sys_prompt": "你是专业的记忆大师，在我的工作中帮助我回忆各种信息，根据上下文回答我的问题"
        })
        logger.info(resp)

if __name__ == '__main__':
    unittest.main()
