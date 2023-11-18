import os
import sys
import logging
import subprocess
import ezkl
import traceback
from dotenv import load_dotenv, find_dotenv
import uuid

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel

class ModelInput(BaseModel):
    inputdata: str
    onnxmodel: str

load_dotenv(find_dotenv())
# flags to only allow for only one proof
# the server cannot accomodate more than one proof
loaded_onnxmodel = None
loaded_inputdata = None
loaded_proofname = None
running = False

WEBHOOK_PORT = int(os.environ.get("PORT", 8080))  # 443, 80, 88 or 8443 (port need to be 'open')
WEBHOOK_LISTEN = '0.0.0.0' 

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

app = FastAPI()
#ezkl = "./ezkl/target/release/ezkl"

# allow cors
app.add_middleware(
    CORSMiddleware,
    #allow_origins=origins,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)

# Class UploadOnnxModel(BaseModel):
    

"""
Upload onnx model for proving, no validation atm
"""
@app.post('/upload/onnxmodel')
def upload_onnxmodel(onnxmodel: UploadFile = File(...)):
    uuidval = uuid.uuid4()
    file_location = f"onnxmodel/{str(uuidval)}.onnx"

    os.makedirs(os.path.dirname(file_location), exist_ok=True)
    with open(file_location, "wb") as f:
        f.write(onnxmodel.file.read())

    return {"file": str(uuidval) + ".onnx"}
        
"""
Upload input data for proving, no validation atm
"""
@app.post('/upload/inputdata')
def upload_inputdata(input_data: UploadFile = File(...)):
    uuidval = uuid.uuid4()
    file_location = f"inputdata/{str(uuidval)}.json"

    os.makedirs(os.path.dirname(file_location), exist_ok=True)
    with open(file_location, "wb") as f:
        f.write(input_data.file.read())

    return {"file": str(uuidval) + ".json"}

"""
Sets the model and input to be used
"""
@app.post('/run/initialize')
async def set_model_input(model_input: ModelInput):
    global loaded_inputdata, loaded_onnxmodel, loaded_proofname, running

    if running:
        raise HTTPException(status_code=400, detail="Already running, please wait for completion")

    loaded_inputdata = os.path.join("inputdata", model_input.inputdata.strip())
    loaded_onnxmodel = os.path.join("onnxmodel", model_input.onnxmodel.strip())

    loaded_proofname = f"inputdata_{loaded_inputdata[10:46]}+onnxmodel_{loaded_onnxmodel[10:46]}"

    return {
        "loaded_inputdata": loaded_inputdata,
        "loaded_onnxmodel": loaded_onnxmodel,
        "proof_name": loaded_proofname
    }

@app.get('/run/initialize')
async def get_model_input():
    if loaded_inputdata is None or loaded_onnxmodel is None:
        raise HTTPException(status_code=404, detail="No model or input data loaded")

    return {
        "loaded_inputdata": loaded_inputdata,
        "loaded_onnxmodel": loaded_onnxmodel,
        "proof_name": loaded_proofname
    }



"""
Generates evm verifier
"""
@app.get('/run/gen_evm_verifier')
async def gen_evm_verifier():
    global loaded_inputdata
    global loaded_onnxmodel
    global loaded_proofname
    global running

    # loaded_inputdata="inputdata/5b9e4019-2b31-4578-850c-8384716cb18a.json"
    # loaded_onnxmodel="onnxmodel/64a18ff9-855d-447f-9926-8ff2d660d3f9.onnx"
    # loaded_proofname="inputdata_5b9e4019-2b31-4578-850c-8384716cb18a+onnxmodel_64a18ff9-855d-447f-9926-8ff2d660d3f9"
    # running=False

    print(loaded_inputdata)
    print(loaded_onnxmodel)
    print(loaded_proofname)
    print(running)
    settings_path = os.path.join('settings.json')
    print(settings_path)
    srs_path = os.path.join('kzg.srs')
    print(srs_path)
    compiled_model_path = os.path.join('network.compiled')
    pk_path = os.path.join('test.pk')
    vk_path = os.path.join('test.vk')
    witness_path = os.path.join('witness.json')


    # if loaded_inputdata is None or loaded_onnxmodel is None or loaded_proofname is None:
    #     return "Input Data or Onnx Model not loaded", 400
    # if running:
    #     return "Already running please wait for completion", 400
    # if os.path.exists(os.path.join(os.getcwd(), "generated", loaded_proofname + ".sol")) and \
    #     os.path.exists(os.path.join(os.getcwd(), "generated", loaded_proofname + ".code")):
    #     return "Verifier already exists", 400
    res = ezkl.gen_settings(loaded_onnxmodel, settings_path)
    assert res == True
    res = await ezkl.calibrate_settings(loaded_inputdata, loaded_onnxmodel, settings_path, "resources")
    assert res == True
    res = ezkl.get_srs(srs_path, settings_path)
    res = ezkl.compile_circuit(loaded_onnxmodel, compiled_model_path, settings_path)
    assert res == True
    # srs path
    res = ezkl.get_srs(srs_path, settings_path)
    res = ezkl.gen_witness(loaded_inputdata, compiled_model_path, witness_path)
    assert os.path.isfile(witness_path)
    
    res = ezkl.setup(
        compiled_model_path,
        vk_path,
        pk_path,
        srs_path,
    )

    assert res == True
    assert os.path.isfile(vk_path)
    assert os.path.isfile(pk_path)
    assert os.path.isfile(settings_path)

    witness_path = os.path.join('witness.json')

    res = ezkl.gen_witness(loaded_inputdata, compiled_model_path, witness_path)
    assert os.path.isfile(witness_path)

    # Generate the proof
    print("generating proof...")
    proof_path = os.path.join('proof.json')

    proof = ezkl.prove(
            witness_path,
            compiled_model_path,
            pk_path,
            proof_path,
            srs_path,
            "single",
        )

    #print(proof)
    assert os.path.isfile(proof_path)

    # verify our proof
    print("verifying proof...")
    res = ezkl.verify(
            proof_path,
            settings_path,
            vk_path,
            srs_path,
        )

    assert res == True
    print("verified")


    sol_code_path = os.path.join('Verifier.sol')
    abi_path = os.path.join('Verifier.abi')

    res = ezkl.create_evm_verifier(
            vk_path,
            srs_path,
            settings_path,
            sol_code_path,
            abi_path
        )

    assert res == True
    assert os.path.isfile(sol_code_path)

    # try:
    #     running = True
    #     print("Generating EVM Verifier")
    #     res = ezkl.gen_settings(loaded_onnxmodel, settings_path)
    #     assert res == True
        
    #     res = await ezkl.calibrate_settings(loaded_inputdata, model_path, settings_path, "resources")  # Optimize for resources

    #     # p = subprocess.run([
    #     #         ezkl,
    #     #         "--bits=16",
    #     #         "-K=17",
    #     #         "create-evm-verifier",
    #     #         "-D", os.path.join(os.getcwd(), loaded_inputdata),
    #     #         "-M", os.path.join(os.getcwd(), loaded_onnxmodel),
    #     #         "--deployment-code-path", os.path.join(os.getcwd(), "generated", loaded_proofname + ".code"),
    #     #         "--params-path=" + os.path.join(os.getcwd(), "kzg.params"),
    #     #         "--vk-path", os.path.join(os.getcwd(), "generated", loaded_proofname + ".vk"),
    #     #         "--sol-code-path", os.path.join(os.getcwd(), "generated", loaded_proofname + ".sol"),
    #     #     ],
    #     #     capture_output=True,
    #     #     text=True
    #     # )
    #     print("Done generating EVM Verifier")
    #     running = False

        # return {
        #     # "stdout": p.stdout,
        #     # "stderr": p.stderr
        # }

    # except:
    #     running = False
    #     err = traceback.format_exc()
    #     return "Something bad happened! Please inform the server admin\n" + err, 500
    return { "message": "win"}


@app.get("/")
async def root():
    return {"message": "Hello World"}

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=WEBHOOK_LISTEN,
        port=WEBHOOK_PORT
    )